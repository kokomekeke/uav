import threading
import time
from queue import Queue
from typing import Any, Optional

from pysagax import BaseConnection
from pysagax.field.loop import Loop


class CSController(Loop, BaseConnection):
    """Background process communicating with CoreService command interface"""

    def __init__(
        self,
        # TODO: Define useful defaults
        address: str = "10.1.1.139",
        port: int = 12936,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        BaseConnection.__init__(self)
        self.host_port = f"{address}:{port}"

        # TODO: Set up control channel to CoreService here
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._sock_thread: Optional[threading.Thread] = None

    def __call__(
        self, queue_in: Queue[Any], queue_out: Queue[Any], *args, **kwargs
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out
        return super()._call(*args, **kwargs)

    def display_status_callback(self, message: str) -> None:
        self._logger.info(message)

    def _pre_loop(self) -> None:
        self.disconnect = False
        self._sock_thread = threading.Thread(target=self._run_socket)
        self._sock_thread.start()
        # TODO: Connect to CoreService here

    def receive_on_socket(self, data: bytes) -> None:
        """
        When text is received on the command socket, send it over in the queue.
        """
        assert self._queue_out is not None
        data_str = data.decode()
        self._logger.debug(data_str)

        self._queue_out.put(data_str)

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None
        # Hang until a new command is received
        command = self._queue_in.get()

        self.send_on_socket(command.encode())
        self._logger.debug(command)
        # response = "132"

        # Send response to Interpreter
        # self._queue_out.put(response)

    def _run_socket(self) -> None:
        # Run the receiver task
        while True:
            self.run_socket()
            # if self.disconnect:
            #     return
            self._logger.warning("Connection to CS lost, reconnecting in 3 seconds")
            time.sleep(3.0)
