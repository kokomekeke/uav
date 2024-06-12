from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue
import sys

from typing import Any, Optional

import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading

import numpy as np

from pysagax.common.loop import Loop

from pysagax.util.protobuf_spectrum_utils import (
    convert_iterable_to_spectrum_data,
    protobuf_spectrum_to_numpy,
    cast_all_spectrums_in_measurement,
)
import pysagax.communication.broadcast as pysagax_broadcast


class PPStreamPreparation(Loop):
    """
    Background process for preparing packets for the streamer.
    Conversions, compressions, and data pruning happens here.
    """

    def __init__(
        self, data_type=proto_data.Spectrum.DataType.FLOAT16, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._data_type: proto_data.Spectrum.DataType.ValueType = data_type
        self._udp_max_size = pysagax_broadcast.MESSAGE_LIMIT

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out

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

    def _calculate_decim_factor(self, meas: proto_data.Measurement) -> int:
        spec_size = sum(len(data_part.data) for data_part in meas.data)
        fixed_size = len(meas.SerializeToString()) - spec_size
        return int(spec_size / (self._udp_max_size - fixed_size) + 1)

    def _shrink_measurement_packet(
        self, meas: proto_data.Measurement, decim_factor: int
    ) -> proto_data.Measurement:
        if decim_factor <= 1:
            return meas
        for i in range(len(meas.data)):
            original_spec_data = protobuf_spectrum_to_numpy(meas.data[i])
            extend_count = decim_factor - (len(original_spec_data) % decim_factor)
            extend_count %= decim_factor
            if extend_count:
                # Count must be divisible by decim factor
                original_spec_data = np.append(
                    original_spec_data, np.full(extend_count, -np.inf)
                )
            decimated_spec_data = np.maximum.reduce(
                [original_spec_data[d::decim_factor] for d in range(decim_factor)]
            )
            meas.data[i].data = convert_iterable_to_spectrum_data(
                decimated_spec_data, meas.data[i].data_type
            )
        return meas

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None

        try:
            packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(packet, proto_data.Measurement)

            packet = self._convert_spectrums(packet)
            packet = self._shrink_measurement_packet(
                packet, self._calculate_decim_factor(packet)
            )
            self._logger.debug(
                f"PostProcessing/Stream preparation finished on packet {packet.packet_id}"
            )
            self._queue_out.put(packet)

        except queue.Empty:
            pass
