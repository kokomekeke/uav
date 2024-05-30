from __future__ import annotations
import logging
from queue import Queue
import time

from typing import Optional
from pysagax.communication.pub_sub import SUB
from pysagax.df.lena_core_service import BaseConnection

from pysagax.common.loop import Loop

from pysagax.message.data_pb2 import Telemetry, Measurement, Event, OperationalError
from pysagax.message.data_types import DataType

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
        self._telemetry_queue_out: Optional[Queue] = None

    def __call__(
        self,
        stream_queue_out: Queue[Telemetry | Measurement | Event | OperationalError],
        telemetry_queue_out: Queue[Telemetry],
        *args,
        **kwargs,
    ) -> None:
        self._stream_queue_out = stream_queue_out
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
        data, data_type = self._sub.recv() or (b"*", "*")
        if data_type == "*":
            return
        data_type_object = DataType(data_type)
        stream_packet = DataType.to_message(data_type_object)
        stream_packet.ParseFromString(data)
        if isinstance(stream_packet, Measurement):
            self._stream_queue_out.put(stream_packet)
        elif isinstance(stream_packet, Telemetry):
            self._protobuf_to_log(stream_packet, "CS TEL {}", logging.DEBUG)
            self._telemetry_queue_out.put(stream_packet)
        else:
            self._protobuf_to_log(stream_packet, "CS Dropped {}", logging.WARNING)

