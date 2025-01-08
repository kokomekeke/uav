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
)
from pysagax.util.queue_put import queue_put
import pysagax.communication.broadcast as pysagax_broadcast


class PPStreamPreparation(Loop):
    """
    Background process for preparing packets for the streamer.
    Conversions, compressions, and data pruning happens here.
    Optionally saves the Measurement packets without the spectrum data to files.
    Decimates the number of outgoing packets by the specified factor.
    Also downsamples the spectrum data in outgoing packets to fit the UDP packet size limit.
    """

    def __init__(
        self,
        data_type=proto_data.Spectrum.DataType.FLOAT16,
        udp_max_size: int = pysagax_broadcast.MESSAGE_LIMIT,
        detection_recording_path: str | None = None,
        decimation_factor: int | None = None,
        max_recording_length: float = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._data_type: proto_data.Spectrum.DataType.ValueType = data_type
        self._udp_max_size = udp_max_size

        self._detection_recording_path: str | None = detection_recording_path
        self._file_streamer: FileStreamer | None = None  # for recording detections

        self._latest_telemetry_proxy: Optional[DictProxy] = None
        self._latest_se_state: Optional[str] = None  # obtained from latest telemetry
        self._recording_start_time: float = 0

        # timeout for starting a new recording file
        # if non-positive -> the program will not split the recording files
        self._max_recording_length: float = max_recording_length

        if not isinstance(decimation_factor, int | None):
            raise ValueError("Only integer decimation factors are supported")
        self._decimation_factor = decimation_factor
        self._dropped_packet_counter: int = 0

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        latest_telemetry_proxy: Optional[DictProxy] = None,
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out

        self._logger.info(
            f"Spectrum data type is {proto_data.Spectrum.DataType.Name(self._data_type)}, byte order {sys.byteorder}"
        )
        self._logger.info(f"Decimation factor is {self._decimation_factor}")

        self._latest_telemetry_proxy = latest_telemetry_proxy
        sleep(2)  # wait for the Telemetry module to initialize
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
        self._logger.debug(
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

    def _get_current_se_state(self):
        """Read and parse the latest telemetry packet to extract ScanEngine state"""
        if (
            self._latest_telemetry_proxy is None
            or "Telemetry" not in self._latest_telemetry_proxy
        ):
            return "UNKNOWN"
        current_telemetry = proto_data.Telemetry()
        current_telemetry = pickle.loads(self._latest_telemetry_proxy["Telemetry"])
        return current_telemetry.scanengine_state

    def _file_streamer_setup(self) -> None:
        """
        Creates a new FileStreamer if needed:
            - at startup
            - after ScanEngine mode has changed
        """
        if self._detection_recording_path is None:
            return  # we don't want to record detections

        current_se_state = self._get_current_se_state()

        if (
            time() - self._recording_start_time < self._max_recording_length
            or self._max_recording_length <= 0
        ) and self._latest_se_state == current_se_state:
            # starting new file not needed
            return

        if self._file_streamer is not None:
            # close old file streamer
            self._file_streamer.close()
            self._file_streamer = None

        # Create new FileStreamer
        try:
            self._recording_start_time = time()
            self._latest_se_state = current_se_state
            start_time_string = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, extension = os.path.splitext(self._detection_recording_path)
            new_path = f"{name}_{start_time_string}_{self._latest_se_state}{extension}"  # Appending a timestamp and scan engine state to file name

            self._file_streamer = FileStreamer(new_path, "record")
            self._logger.info(f"Detection recording will be saved to '{new_path}'")
        except Exception as e:
            self._logger.error("Couldn't create detection recorder: ", e)
        # TODO: new FileStreamer at scan plan change

    def _record_packet(self, packet: proto_data.Measurement) -> None:
        """
        Records the detections if they need to be (recording path is set)
        Modifies packets in place (deletes spectrum data) so this function should be called last in _loop()
        """
        self._file_streamer_setup()
        if self._file_streamer is None:
            return

        try:
            del packet.data[:]  # Remove spectrums. We're not making spectrograms here.
            self._file_streamer.put(packet)
        except Exception as e:
            self._logger.error("Detection recording:", e)

    def _stream_packet(self, packet):
        """
        Decides if the packet needs to be streamed based on decimation factor.
        If so, it prepares the packet and puts it in the queue to Streamer.
        """
        if self._decimation_factor is not None:
            if self._dropped_packet_counter < self._decimation_factor - 1:
                self._dropped_packet_counter += 1
                return

        packet = self._convert_spectrums(packet)
        packet = self._shrink_measurement_packet(
            packet, self._calculate_downsample_factor(packet)
        )
        queue_put(self._queue_out, packet, 0.1, logger=self._logger)
        self._dropped_packet_counter = 0

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None

        try:
            packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(packet, proto_data.Measurement)

            self._stream_packet(packet)

            self._logger.debug(
                f"PostProcessing/Stream preparation finished on packet {packet.packet_id}"
            )

            # saving post processing results to file
            self._record_packet(packet)

        except queue.Empty:
            pass
