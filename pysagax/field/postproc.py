from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue
import sys

from typing import Any, Optional

import numpy


import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading

from pysagax.common.loop import Loop


class PostProc(Loop):
    """Background process for CoreService stream packets post processing tasks and creating Measurement packets"""

    def __init__(
        self, data_type=proto_data.Spectrum.DataType.INT16, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._conf_queue_in: Optional[Queue] = None
        self._conf_queue_out: Optional[Queue] = None
        self._meas_queue_in: Optional[Queue] = None
        self._comm_queue_out: Optional[Queue] = None
        self._heading_queue_in: Optional[Queue] = None
        self._np_data_type: Optional[numpy.dtype] = None
        self._data_type = data_type
        self._latest_config_id_value: Optional[ValueProxy[int]] = None
        self._latest_heading: Optional[proto_heading.HeadingData] = None

    def __call__(
        self,
        comm_queue_out: Queue[Any],
        meas_queue_in: Queue[Any],
        conf_queue_in: Queue[Any],
        conf_queue_out: Queue[Any],
        heading_queue_in: Queue[Any],
        latest_config_id_value: Optional[ValueProxy[int]] = None,
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_out = comm_queue_out
        self._meas_queue_in = meas_queue_in
        self._conf_queue_in = conf_queue_in
        self._conf_queue_out = conf_queue_out
        self._heading_queue_in = heading_queue_in
        self._latest_config_id_value = latest_config_id_value
        self._np_data_type = {
            proto_data.Spectrum.DataType.INT16: numpy.dtype(numpy.int16),
            proto_data.Spectrum.DataType.INT8: numpy.dtype(numpy.int8),
            proto_data.Spectrum.DataType.FLOAT32: numpy.dtype(numpy.float32),
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
            sp_clip = numpy.clip(
                numpy.frombuffer(spectrum_old.data, dtype=numpy.float32),
                self._np_data_type_lims[0],
                self._np_data_type_lims[1],
            )
            if spectrum_new.spectrum_type in [
                proto_data.Spectrum.SpectrumType.AZIMUTH,
                proto_data.Spectrum.SpectrumType.ELEVATION,
            ]:
                # Representing angles as integers: use full scale (or degrees?)
                # sp_clip = sp_clip * self._np_data_type_lims[1] / numpy.pi
                sp_clip = sp_clip * 180 / numpy.pi
            spectrum_new.data = sp_clip.astype(self._np_data_type).tobytes()
            converted_spectrums.append(spectrum_new)

        del meas.data[:]
        meas.data.extend(converted_spectrums)
        return meas

    def _loop(self) -> None:
        assert self._comm_queue_out is not None
        assert self._meas_queue_in is not None
        assert self._conf_queue_in is not None
        assert self._conf_queue_out is not None
        assert self._heading_queue_in is not None
        # Hang until a new command is received
        try:
            conf_request = self._conf_queue_in.get(timeout=0, block=False)
            self._protobuf_to_log(conf_request)
            self._conf_queue_out.put(None)
        except queue.Empty:
            pass
        # Execute command

        while True:
            try:
                heading_packet = self._heading_queue_in.get_nowait()
                if heading_packet is not None:
                    self._latest_heading = heading_packet
            except queue.Empty:
                break
        try:
            meas_packet = self._meas_queue_in.get(block=True, timeout=1)
            assert isinstance(meas_packet, proto_data.Measurement)

            meas_packet = self._convert_spectrums(meas_packet)

            if self._latest_heading is not None:
                meas_packet.heading_data.CopyFrom(self._latest_heading)
            if self._latest_config_id_value is not None:
                meas_packet.config_id = self._latest_config_id_value.get()

            self._logger.debug(f"PostProc finished on packet {meas_packet.packet_id}")
            self._comm_queue_out.put(meas_packet)

        except queue.Empty:
            pass
        # Send response to Communicator
