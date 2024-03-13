from __future__ import annotations
from queue import Empty, Queue
import queue
import time

from typing import Any, Optional
from pysagax.df.lena_core_service import BaseConnection

from pysagax.field.loop import Loop


class CSStreamer(Loop, BaseConnection):

    def __init__(
        self,
        address: str = "127.0.0.1",
        port: int = 12937,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        BaseConnection.__init__(self)
        self.host_port = f"{address}:{port}"
        self._stream_queue_out: Optional[Queue] = None

    def __call__(
        self,
        stream_queue_out: Queue[bytes],
        *args,
        **kwargs,
    ) -> None:
        self._stream_queue_out = stream_queue_out
        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        while True:
            self.run_socket()
            self._logger.warning(
                "Connection to CS Stream lost, reconnecting in 3 seconds"
            )
            time.sleep(3.0)

    def display_status_callback(self, message: str) -> None:
        self._logger.info(message)

    def receive_on_socket(self, data: bytes) -> None:
        """
        When text is received on the command socket, send it over in the queue.
        """
        assert self._stream_queue_out is not None

        self._stream_queue_out.put(data)
