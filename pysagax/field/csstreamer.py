from __future__ import annotations
import logging
from queue import Queue
import time

from typing import Optional
from pysagax.communication.pub_sub import SUB

from pysagax.common.loop import Loop

from pysagax.message.data_pb2 import (
    Telemetry,
    Measurement,
    Event,
    OperationalError,
    SoundSignal,
)
from pysagax.message.data_types import DataType

from pysagax.util.queue_put import queue_put


class CSStreamer(Loop):
    """Background process for connecting to the CoreService stream interface and receiving binary data from there"""

    def __init__(
        self,
        address: str = "127.0.0.1",
        port: int = 12937,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        self._host = address
        self._port = port
        self._sub: Optional[SUB] = None
        self._stream_queue_out: Optional[Queue] = None
        self._audio_stream_queue_out: Optional[Queue] = None
        self._telemetry_queue_out: Optional[Queue] = None

    def __call__(
        self,
        stream_queue_out: Queue[Telemetry | Measurement | Event | OperationalError],
        audio_stream_queue_out: Queue[list[SoundSignal]],
        telemetry_queue_out: Queue[Telemetry],
        *args,
        **kwargs,
    ) -> None:
        self._stream_queue_out = stream_queue_out
        self._audio_stream_queue_out = audio_stream_queue_out
        self._telemetry_queue_out = telemetry_queue_out
        self._logger.info(f"ZMQ SUB connecting to ZMQ PUB on {self._host}:{self._port}")
        self._sub = SUB(self._host, self._port)
        all_groups = [group.value for group in DataType]
        self._sub.connect(group=all_groups)
        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        assert self._sub is not None
        assert self._stream_queue_out is not None
        assert self._telemetry_queue_out is not None

        message = self._sub.recv(timeout=500)
        if message is None:
            self._logger.critical(f"No packet received from CS for 0.5s")
            return
        data, data_type = message

        data_type_object = DataType(data_type)
        stream_packet = DataType.to_message(data_type_object)
        stream_packet.ParseFromString(data)
        if isinstance(stream_packet, Measurement):
            if len(stream_packet.sound_signal):
                # If there is audio stream then remove it from stream_packet and direct it to SoundStreamProcessor
                sound_signal_list = [ss for ss in stream_packet.sound_signal]
                queue_put(
                    self._audio_stream_queue_out,
                    sound_signal_list,
                    0,
                    self._logger,
                    "Stream audio queue out",
                )
                del stream_packet.sound_signal[:]
                if len(stream_packet.detection) == 0 and len(stream_packet.data) == 0:
                    # the packet only contained audio data, so no need to send it to post processing
                    self._logger.trace("Measurement packet not sent to post processing")
                    return
            queue_put(
                self._stream_queue_out,
                stream_packet,
                0,
                self._logger,
                "Stream queue out",
            )
        elif isinstance(stream_packet, Telemetry):
            self._protobuf_to_log(stream_packet, "CS TEL {}", logging.DEBUG)
            queue_put(
                self._telemetry_queue_out,
                stream_packet,
                0,
                self._logger,
                "Telemetry queue out",
            )
        else:
            self._protobuf_to_log(stream_packet, "CS Dropped {}", logging.WARNING)
