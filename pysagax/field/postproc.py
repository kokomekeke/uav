from __future__ import annotations
from queue import Empty, Queue
import queue

from typing import Any, Optional

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data

from pysagax.field.loop import Loop


class PostProc(Loop):

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._cmd_timeout_seconds = 30.0
        self.config_id = 0
        self._comm_queue_in: Optional[Queue] = None
        self._comm_queue_out: Optional[Queue] = None
        self._cs_queue_in: Optional[Queue] = None
        self._cs_queue_out: Optional[Queue] = None

    def __call__(
        self,
        comm_queue_out: Queue[Any],
        cs_queue_in: Queue[Any],
        conf_queue_in: Queue[Any],
        conf_queue_out: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_out = comm_queue_out
        self._cs_queue_in = cs_queue_in
        self._conf_queue_in = conf_queue_in
        self._conf_queue_out = conf_queue_out
        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        # Hang until a new command is received
        try:
            conf_request = self._conf_queue_in.get(timeout=0, block=False)
        except queue.Empty:
            pass
        # Execute command
        try:
            cs_stream_packet = self._cs_queue_in.get(block=True, timeout=1)
            measurement = proto_data.Measurement()

            measurement_raw = measurement.SerializeToString()
            self._comm_queue_out.put(response)
        except queue.Empty:
            pass
        # Send response to Communicator

    def _process(self, raw_command: bytes) -> bytes:
        """Interpret, route and execute incoming commands"""
