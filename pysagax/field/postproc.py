from __future__ import annotations
import datetime
import multiprocessing
from multiprocessing.managers import ValueProxy
from queue import Empty, Queue
import queue
import re
import sys

from typing import Any, Optional

import numpy
from pysagax.df.lena_core_service import (
    CoreServiceDebugPacket,
    CoreServicePacket,
    CoreServiceROIResultPacket,
    CoreServiceSpectrumPacket,
)

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data

from pysagax.field.loop import Loop


class PostProc(Loop):

    def __init__(
        self, data_type=proto_data.Spectrum.DataType.INT16, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._conf_queue_in: Optional[Queue] = None
        self._conf_queue_out: Optional[Queue] = None
        self._cs_queue_in: Optional[Queue] = None
        self._comm_queue_out: Optional[Queue] = None
        self._np_data_type: Optional[numpy.dtype] = None
        self._data_type = data_type
        self._measurement_packet = proto_data.Measurement()
        self._packet_id_counter: int = 0
        self._latest_config_id_value: Optional[ValueProxy[int]] = None

    def __call__(
        self,
        comm_queue_out: Queue[Any],
        cs_queue_in: Queue[Any],
        conf_queue_in: Queue[Any],
        conf_queue_out: Queue[Any],
        latest_config_id_value: Optional[ValueProxy[int]] = None,
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_out = comm_queue_out
        self._cs_queue_in = cs_queue_in
        self._conf_queue_in = conf_queue_in
        self._conf_queue_out = conf_queue_out
        self._latest_config_id_value = latest_config_id_value
        self._np_data_type = {
            proto_data.Spectrum.DataType.INT16: numpy.dtype(numpy.int16),
            proto_data.Spectrum.DataType.INT8: numpy.dtype(numpy.int8),
            proto_data.Spectrum.DataType.FLOAT32: numpy.dtype(numpy.float32),
        }[self._data_type]
        self._logger.info(
            f"Spectrum data type is {self._np_data_type.name}, byte order {sys.byteorder}"
        )

        return super()._call(*args, **kwargs)

    def _handle_spectrum_packet(self, cs_packet: CoreServiceSpectrumPacket) -> None:
        spectrum = proto_data.Spectrum()
        spectrum.spectrum_type = proto_data.Spectrum.SpectrumType.MAGNITUDE
        spectrum.data_type = self._data_type
        spectrum.channel_id = cs_packet.stream_id
        spectrum.data = cs_packet.magnitude_spectrum.astype(
            self._np_data_type
        ).tobytes()
        spectrum.center_frequency = cs_packet.center_frequency
        spectrum.bandwidth = cs_packet.iq_rate
        self._measurement_packet.data.append(spectrum)

    def _handle_roi_packet(self, cs_packet: CoreServiceROIResultPacket) -> None:
        detection = proto_data.Detection()
        detection.roi_id = 0
        detection.frequency = cs_packet.center_frequency
        detection.bandwidth = cs_packet.span
        detection.strength = cs_packet.roi_level
        detection.azimuth = cs_packet.roi_azimuth
        detection.elevation = cs_packet.roi_elevation
        self._measurement_packet.detection.append(detection)

    def _decode_iso_datetime(self, isoformat: str) -> Optional[datetime.datetime]:
        try:
            return datetime.datetime.fromisoformat(isoformat)
        except ValueError:
            try:
                return datetime.datetime.strptime(isoformat, "%Y-%m-%dT%H:%M:%S.%f%z")
            except ValueError:
                return None

    def _handle_debug_packet(self, cs_packet: CoreServiceDebugPacket) -> None:
        if cs_packet.title == "peaks":
            regex = r"peak(\d+)=(\d+)"
            matches = re.findall(
                regex, str(cs_packet.contents.decode())
            )  # creating a list of (ChannelID, PeakValue) tuples from the debug message
            peaks = [int(peak[1]) for peak in matches]
            self._measurement_packet.peaks.extend(peaks)
        elif cs_packet.title == "t":
            dt = self._decode_iso_datetime(cs_packet.contents.decode())
            if dt is None:
                self._logger.warning(
                    f"Cannot decode timestamp {cs_packet.contents.decode()} "
                )
                return
            self._measurement_packet.time.FromDatetime(dt)
            self._logger.debug(
                f"Timestamp {cs_packet.contents.decode()} = {self._measurement_packet.time.ToJsonString()}"
            )

    def _push_finished_packet(self) -> None:
        assert self._comm_queue_out is not None
        self._measurement_packet.stream_id = 0
        self._packet_id_counter += 1
        self._measurement_packet.packet_id = self._packet_id_counter
        if self._latest_config_id_value is not None:
            self._measurement_packet.config_id = self._latest_config_id_value.get()
        self._logger.debug(f"PostProc finished on packet {self._packet_id_counter}")
        self._comm_queue_out.put(self._measurement_packet)
        self._measurement_packet = proto_data.Measurement()

    def _loop(self) -> None:
        assert self._comm_queue_out is not None
        assert self._cs_queue_in is not None
        assert self._conf_queue_in is not None
        assert self._conf_queue_out is not None
        # Hang until a new command is received
        try:
            conf_request = self._conf_queue_in.get(timeout=0, block=False)
            self._logger.info(vars(conf_request))
        except queue.Empty:
            pass
        # Execute command
        try:
            cs_stream_packet = self._cs_queue_in.get(block=True, timeout=1)
            assert isinstance(cs_stream_packet, CoreServicePacket)
            if isinstance(cs_stream_packet, CoreServiceSpectrumPacket):
                self._handle_spectrum_packet(cs_stream_packet)
            elif isinstance(cs_stream_packet, CoreServiceROIResultPacket):
                self._handle_roi_packet(cs_stream_packet)
            elif isinstance(cs_stream_packet, CoreServiceDebugPacket):
                self._handle_debug_packet(cs_stream_packet)
                if cs_stream_packet.title == "t":  # timestamp is the last packet
                    self._push_finished_packet()
        except queue.Empty:
            pass
        # Send response to Communicator
