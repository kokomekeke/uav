from __future__ import annotations
from multiprocessing.managers import DictProxy
import pickle
from time import time, sleep
from queue import Queue
import queue
from datetime import datetime
import os
import sys

from typing import Any, Optional

import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading
from pysagax.message.proto_stream_to_file import FileStreamer

import numpy as np

from pysagax.common.loop import Loop

from pysagax.util.protobuf_spectrum_utils import (
    convert_iterable_to_spectrum_data,
    protobuf_spectrum_to_numpy,
    cast_all_spectrums_in_measurement,
    compress_spectrum_data,
)
from pysagax.util.queue_put import queue_put
import pysagax.communication.broadcast as pysagax_broadcast


class PPStreamPreparation(Loop):
    """
    Background process for preparing packets for the streamer.
    Conversions, compressions, and data pruning happens here.
    Decimates the number of outgoing packets by the specified factor.
    Also downsamples the spectrum data in outgoing packets to fit the UDP packet size limit.
    After downsampling it further compresses the spectrum data using zlib (this usually means a 25% further size decrease)
    """

    def __init__(
        self,
        data_type=proto_data.Spectrum.DataType.FLOAT16,
        udp_max_size: int = pysagax_broadcast.MESSAGE_LIMIT,
        spectrum_interval: float | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out_streamer: Optional[Queue] = None  # Queue to streamer
        self._queue_out_rec: Optional[Queue] = None  # Queue to DetectionRecorder
        self._data_type: proto_data.Spectrum.DataType.ValueType = data_type
        self._udp_max_size = udp_max_size

        self._spectrum_interval = spectrum_interval
        self._logger.info(
            f"\nPostProcessing-Stream Preparation module initialized with the following parameters:"
            f"\n\tSpectrum streaming interval = {self._spectrum_interval}"
            f"\n\tSpectrum streaming datatype = {proto_data.Spectrum.DataType.Name(self._data_type)}"
        )

        self._last_spectrum_sent = 0  # timestamp for latest

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out_streamer: Queue[Any],
        queue_out_rec: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out_streamer = queue_out_streamer
        self._queue_out_rec = queue_out_rec

        self._logger.info(
            f"Spectrum data type is {proto_data.Spectrum.DataType.Name(self._data_type)}, byte order {sys.byteorder}"
        )

        return super()._call(*args, **kwargs)

    def _convert_spectrums(
        self, meas: proto_data.Measurement
    ) -> proto_data.Measurement:
        """Converts spectrum data from float to self._data_type and filters out unneeded spectrums"""
        wanted_types = [
            proto_data.Spectrum.SpectrumType.MAGNITUDE,
            # proto_data.Spectrum.SpectrumType.AZIMUTH,
            # proto_data.Spectrum.SpectrumType.ELEVATION
        ]  # TODO: set from config or client. Maybe set the desired magnitude channel too

        for i in reversed(range(len(meas.data))):
            # Deleting unwanted spectrums before streaming
            if meas.data[i].spectrum_type not in wanted_types:
                del meas.data[i]

        cast_all_spectrums_in_measurement(
            measurement=meas, dtype=self._data_type, inplace=True
        )

        return meas

    def _calculate_downsample_factor(self, meas: proto_data.Measurement) -> int:
        """
        Calculate downsampling factor for the measurement packet so that the
        data will fit in the UDP packet size limit.
        """
        spec_size = sum(len(data_part.data) for data_part in meas.data)
        fixed_size = len(meas.SerializeToString()) - spec_size
        downsample_factor = int(spec_size / (self._udp_max_size - fixed_size) + 1)
        self._logger.trace(
            f"Measurement packet downsample_factor={downsample_factor}"
            f"from fix_size={fixed_size} and spec_size={spec_size}"
            f"(max_size={self._udp_max_size})"
        )
        return downsample_factor

    def _shrink_measurement_packet(
        self, meas: proto_data.Measurement, downsample_factor: int
    ) -> proto_data.Measurement:
        """Downsample all spectrums in the packet using maximum value"""
        if downsample_factor <= 1:
            return meas
        for i in range(len(meas.data)):
            original_spec_data = protobuf_spectrum_to_numpy(meas.data[i])
            end_index = len(original_spec_data)
            end_index = end_index - end_index % downsample_factor

            downsampled_spec_data = np.maximum.reduce(
                [
                    original_spec_data[d:end_index:downsample_factor]
                    for d in range(downsample_factor)
                ]
            )
            # Reduce with maximum - we want to see the peaks on the magnitude spectrum
            # In the case of angle spectrums it should not matter that much
            # TODO: the values taken from the spectums will not necessarily be from
            #       the exact same bin
            meas.data[i].data = convert_iterable_to_spectrum_data(
                downsampled_spec_data, meas.data[i].data_type
            )
            self._logger.debug(
                f"Shrinked spectrum data no. {i} from len={len(original_spec_data)} to "
                f"{len(downsampled_spec_data)} (factor={downsample_factor}, end_index={end_index}"
            )
        return meas

    def _record_packet(self, packet: proto_data.Measurement) -> None:
        """
        Forwards the packets to DetectionRecorder
        Modifies packets in place (deletes spectrum data) so this function should be called last in _loop()
        """
        del packet.data[:]  # Remove spectrums. We're not making spectrograms here.
        queue_put(
            self._queue_out_rec,
            packet,
            0,
            logger=self._logger,
            message="[StreamPrep to DetectionRecorder]",
        )

    def _stream_packet(self, packet):
        """
        Prepares the packet based on the settings and puts it in the queue to Streamer.
        """

        current_time = time()
        if current_time - self._last_spectrum_sent > self._spectrum_interval:
            # Prepare spectrum for streaming
            packet = self._convert_spectrums(packet)
            packet = self._shrink_measurement_packet(
                packet, self._calculate_downsample_factor(packet)
            )
            packet = compress_spectrum_data(packet)
            self._last_spectrum_sent = current_time
        else:
            # delete spectrum if not needed
            del packet.data[:]

        packet = self._convert_spectrums(packet)
        packet = self._shrink_measurement_packet(
            packet, self._calculate_downsample_factor(packet)
        )
        queue_put(
            self._queue_out_streamer,
            packet,
            0,
            logger=self._logger,
            message="[StreamPrep to Streamer]",
        )

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out_streamer is not None
        assert self._queue_out_rec is not None

        try:
            packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(packet, proto_data.Measurement)

            self._stream_packet(packet)

            self._logger.trace(
                f"PostProcessing/Stream preparation finished on packet {packet.packet_id}"
            )

            # saving post processing results to file
            self._record_packet(packet)

        except queue.Empty:
            pass
