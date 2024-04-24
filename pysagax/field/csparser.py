from __future__ import annotations
from queue import Queue

import datetime
from typing import Optional

import re
import numpy
from pysagax.df.lena_core_service import CoreServiceParser

from pysagax.common.loop import Loop
from pysagax.df.lena_core_service import (
    CoreServiceDebugPacket,
    CoreServiceROIResultPacket,
    CoreServiceSpectrumPacket,
)

import pysagax.message.data_pb2 as proto_data


class CSParser(Loop, CoreServiceParser):
    """Background process for converting binary CoreService packets to python objects"""

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        CoreServiceParser.__init__(self)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._packet_id_counter: int = 0
        self._measurement_packet = proto_data.Measurement()

    def __call__(
        self,
        queue_in: Queue[bytes],
        queue_out: Queue[bytes],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out
        return super()._call(*args, **kwargs)

    def _handle_spectrum_packet(self, cs_packet: CoreServiceSpectrumPacket) -> None:
        spectrum_defs = [
            (proto_data.Spectrum.SpectrumType.MAGNITUDE, cs_packet.magnitude_spectrum),
            (proto_data.Spectrum.SpectrumType.AZIMUTH, cs_packet.azimuth_spectrum),
            (proto_data.Spectrum.SpectrumType.ELEVATION, cs_packet.elevation_spectrum),
        ]
        for spectrum_type, cs_spectrum in spectrum_defs:
            spectrum = proto_data.Spectrum()
            spectrum.spectrum_type = spectrum_type
            spectrum.data_type = proto_data.Spectrum.DataType.FLOAT32
            spectrum.channel_id = cs_packet.stream_id
            spectrum.data = cs_spectrum.astype(numpy.dtype(numpy.float32)).tobytes()
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
        assert self._queue_out is not None
        dropped_msg = (
            "Packet does not contain {} data. "
            "CoreService likely dropped it due to slow PySAGAX-UAV performance. "
            "Instead of sending, wait one more cycle to get a full packet."
        )
        if len(self._measurement_packet.data) == 0:
            self._logger.warning(dropped_msg.format("spectrum data"))
            return
        if len(self._measurement_packet.peaks) == 0:
            self._logger.warning(dropped_msg.format("peaks"))
            return

        self._measurement_packet.stream_id = 0
        self._packet_id_counter += 1
        self._measurement_packet.packet_id = self._packet_id_counter

        self._logger.debug(f"CSParser finished on packet {self._packet_id_counter}")
        self._queue_out.put(self._measurement_packet)
        self._measurement_packet = proto_data.Measurement()

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None
        data = self._queue_in.get(block=True)
        for cs_packet in self.extract_packets(data):
            if isinstance(cs_packet, CoreServiceSpectrumPacket):
                self._handle_spectrum_packet(cs_packet)
            elif isinstance(cs_packet, CoreServiceROIResultPacket):
                self._handle_roi_packet(cs_packet)
            elif isinstance(cs_packet, CoreServiceDebugPacket):
                self._handle_debug_packet(cs_packet)
                if cs_packet.title == "t":  # timestamp is the last packet
                    self._push_finished_packet()
