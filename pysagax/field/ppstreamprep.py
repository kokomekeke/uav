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

from pysagax.util.protobuf_spectrum_utils import protobuf_spectrum_to_numpy


class PPStreamPreparation(Loop):
    """
    Background process for preparing packets for the streamer.
    Conversions, compressions, and data pruning happens here.
    """

    def __init__(
        self, data_type=proto_data.Spectrum.DataType.INT16, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._np_data_type: Optional[np.dtype] = None
        self._data_type = data_type

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out

        self._np_data_type = {
            proto_data.Spectrum.DataType.INT16: np.dtype(np.int16),
            proto_data.Spectrum.DataType.INT8: np.dtype(np.int8),
            proto_data.Spectrum.DataType.FLOAT32: np.dtype(np.float32),
        }[self._data_type]
        self._np_data_type_lims: tuple[float, float] = {
            proto_data.Spectrum.DataType.INT16: (-32768, 32767),
            proto_data.Spectrum.DataType.INT8: (-128, 127),
            proto_data.Spectrum.DataType.FLOAT32: (None, None),
        }[self._data_type]
        self._logger.info(
            f"Spectrum data type is {self._np_data_type.name}, byte order {sys.byteorder}"
        )

        return super()._call(*args, **kwargs)

    def _convert_spectrums(
        self, meas: proto_data.Measurement
    ) -> proto_data.Measurement:
        """Converts spectrum data from float to self._data_type and filters out unneeded spectrums"""
        converted_spectrums: list = []
        wanted_types = [
            proto_data.Spectrum.SpectrumType.MAGNITUDE,
            # proto_data.Spectrum.SpectrumType.AZIMUTH,
            # proto_data.Spectrum.SpectrumType.ELEVATION
        ]  # TODO: set from config or client. Maybe set the desired magnitude channel too
        for spectrum_old in meas.data:
            if spectrum_old.spectrum_type not in wanted_types:
                continue
            spectrum_new = proto_data.Spectrum()
            spectrum_new.spectrum_type = spectrum_old.spectrum_type
            spectrum_new.data_type = self._data_type
            spectrum_new.channel_id = spectrum_old.channel_id
            spectrum_new.center_frequency = spectrum_old.center_frequency
            spectrum_new.bandwidth = spectrum_old.bandwidth
            sp_clip = np.clip(
                protobuf_spectrum_to_numpy(spectrum_old),
                self._np_data_type_lims[0],
                self._np_data_type_lims[1],
            )
            if spectrum_new.spectrum_type in [
                proto_data.Spectrum.SpectrumType.AZIMUTH,
                proto_data.Spectrum.SpectrumType.ELEVATION,
            ]:
                # Representing angles as integers: use full scale (or degrees?)
                # sp_clip = sp_clip * self._np_data_type_lims[1] / numpy.pi
                sp_clip = sp_clip * 180 / np.pi
            spectrum_new.data = sp_clip.astype(self._np_data_type).tobytes()
            converted_spectrums.append(spectrum_new)

        del meas.data[:]
        meas.data.extend(converted_spectrums)
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
