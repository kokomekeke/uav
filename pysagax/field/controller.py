import time
from queue import Queue

from pysagax import BaseConnection
from pysagax.field.loop import Loop


class CSController(Loop, BaseConnection):
    """Background process communicating with CoreService command interface"""

    def __init__(
        self,
        queue_in: Queue[str],
        queue_out: Queue[str],
        # TODO: Define useful defaults
        address: str = "10.1.1.139",
        port: int = 12936,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        BaseConnection.__init__(self)
        self.host_port = f"{address}:{port}"
        self._queue_in = queue_in
        self._queue_out = queue_out

        # TODO: Set up control channel to CoreService here

    def display_status_callback(self, message: str) -> None:
        self._logger.info(message)

    def _pre_loop(self) -> None:
        self.disconnect = False

        # TODO: Connect to CoreService here

    def receive_on_socket(self, data: bytes) -> None:
        """
        When text is received on the command socket, send it over in the queue.
        """
        data_str = data.decode()
        self._logger.debug(data_str)
        self._queue_out.put(data_str)

    def _loop(self) -> None:
        # Hang until a new command is received
        command = self._queue_in.get()

        self.send_on_socket(command.encode())
        self._logger.debug(command)
        # response = "132"

        # Send response to Interpreter
        # self._queue_out.put(response)


class CSReceiveTask(Loop):
    def __init__(self, cs_controller: CSController, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cs_controller = cs_controller

    def _pre_loop(self) -> None:
        self.disconnect = False

    def _loop(self) -> None:
        # Run the receiver task
        self.cs_controller.run_socket()
        self._logger.warning("Connection to CS lost, reconnecting in 3 seconds")
        time.sleep(3.0)
