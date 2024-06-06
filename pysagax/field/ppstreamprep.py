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
    protobuf_spectrum_to_numpy,
    cast_all_spectrums_in_measurement,
)


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

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None

        try:
            packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(packet, proto_data.Measurement)

            packet = self._convert_spectrums(packet)

            self._logger.debug(
                f"PostProcessing/Stream preparation finished on packet {packet.packet_id}"
            )
            self._queue_out.put(packet)

        except queue.Empty:
            pass
