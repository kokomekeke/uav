import threading
import time
from queue import Queue
from typing import Any, Optional

from pysagax.df.lena_core_service import BaseConnection
from pysagax.field.loop import Loop


class CSController(Loop, BaseConnection):
    """Background process communicating with CoreService command interface"""

    def __init__(
        self,
        # TODO: Define useful defaults
        address: str = "127.0.0.1",
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
        self._queue_in_status: Optional[Queue] = None
        self._queue_out_status: Optional[Queue] = None

        self._queue_of_resp_queues: Optional[Queue[tuple[str, Queue[Any], str]]] = None
        self._merged_queue: Optional[Queue[tuple[str, Queue[Any], str]]] = None

        self._sock_thread: Optional[threading.Thread] = None
        self._queue_primary_thread: Optional[threading.Thread] = None
        self._queue_status_thread: Optional[threading.Thread] = None
        self.response_buffer: str = ""
        self.allowed_to_send: bool = False

    def __call__(
        self,
        queue_in_primary: Queue[Any],
        queue_out_primary: Queue[Any],
        queue_in_status: Optional[Queue[Any]] = None,
        queue_out_status: Optional[Queue[Any]] = None,
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in_primary
        self._queue_out = queue_out_primary
        self._queue_in_status = queue_in_status
        self._queue_out_status = queue_out_status

        self._queue_of_resp_queues = Queue()
        self._merged_queue = Queue()

        return super()._call(*args, **kwargs)

    def display_status_callback(self, message: str) -> None:
        self._logger.info(message)

    def _pre_loop(self) -> None:
        self.disconnect = False
        self._sock_thread = threading.Thread(target=self._run_socket)
        self._queue_primary_thread = threading.Thread(
            target=self._queue_watcher,
            args=(self._queue_in, self._queue_out, "primary"),
        )
        self._queue_status_thread = threading.Thread(
            target=self._queue_watcher,
            args=(self._queue_in_status, self._queue_out_status, "status"),
        )
        self._sock_thread.start()
        self._queue_primary_thread.start()
        self._queue_status_thread.start()
        self.connected_callback = self._connected_callback
        while not self.allowed_to_send:
            self._logger.info("Waiting for CS command...")
            time.sleep(0.5)
        self._logger.info("CoreService command operational")

    def _connected_callback(self) -> None:
        self._logger.info("Timeout for flushing CoreService socket.")
        time.sleep(
            1.5
        )  # Flush any incoming data from coreservice before sending commands
        self.allowed_to_send = True
        self._logger.info("Allowed to send commands.")

    def _queue_watcher(
        self, input_queue: Queue[Any], output_queue: Queue[Any], label: str = "queue"
    ) -> None:
        assert self._merged_queue is not None
        while True:
            command: str = input_queue.get()
            for single_command in command.split(";"):
                single_command = single_command.strip()
                if single_command:
                    self._logger.debug(f"Command {single_command} on {label}")
                    self._merged_queue.put((single_command + ";", output_queue, label))

    def receive_on_socket(self, data: bytes) -> None:
        """
        When text is received on the command socket, send it over in the queue.
        """
        assert self._queue_out is not None
        assert self._queue_of_resp_queues is not None

        if self._queue_of_resp_queues.empty():
            self._logger.error(
                f'No command in the queue, still got a response on the socket: "{data.decode()}"'
            )
            return
        data_str = data.decode()
        self.response_buffer += data_str
        index = self.response_buffer.find(";")
        while -1 < index:
            resp = self.response_buffer[: index + 1]
            # self._logger.debug(resp)
            command, resp_queue, label = self._queue_of_resp_queues.get()
            self._logger.debug(f"Response {resp} to {label} ({command})")
            resp_queue.put(resp)
            # self._queue_out.put(resp)
            self.response_buffer = self.response_buffer[index + 1 :]
            index = self.response_buffer.find(";")

    def _loop(self) -> None:
        assert self._merged_queue is not None
        assert self._queue_of_resp_queues is not None
        # Hang until a new command is received
        command, out_queue, label = self._merged_queue.get()
        self._queue_of_resp_queues.put((command, out_queue, label))
        success = self.send_on_socket(command.encode())
        if not success:
            self._logger.warning(
                f"Tried to send command {command} ({label}). Socket error."
            )
        # self._logger.debug(command)
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
