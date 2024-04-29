import threading
import time
from queue import Queue
from typing import Any, Optional

from pysagax.common.loop import Loop

import pysagax.message.command_pb2 as proto_cmd
from pysagax.communication.req_rep_tcp import REQ


class CSCommand(Loop):
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
        self.host_port = f"{address}:{port}"
        self._address_server = address
        self._port_server = port

        # TODO: Set up control channel to CoreService here
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        # self._queue_in_status: Optional[Queue] = None
        # self._queue_out_status: Optional[Queue] = None

        self._queue_of_resp_queues: Optional[Queue[tuple[str, Queue[Any], str]]] = None
        self._merged_queue: Optional[Queue[tuple[str, Queue[Any], str]]] = None

        self._sock_thread: Optional[threading.Thread] = None
        self._queue_primary_thread: Optional[threading.Thread] = None
        self._queue_status_thread: Optional[threading.Thread] = None
        self.response_buffer: str = ""
        self.allowed_to_send: bool = False

        self._req: Optional[REQ] = None

    def __call__(
        self,
        queue_in_primary: Queue[Any],
        queue_out_primary: Queue[Any],
        # queue_in_status: Optional[Queue[Any]] = None,
        # queue_out_status: Optional[Queue[Any]] = None,
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in_primary
        self._queue_out = queue_out_primary
        # self._queue_in_status = queue_in_status
        # self._queue_out_status = queue_out_status

        self._req = REQ(self._address_server, self._port_server)

        self._queue_of_resp_queues = Queue()
        self._merged_queue = Queue()

        return super()._call(*args, **kwargs)

    def display_status_callback(self, message: str) -> None:
        self._logger.info(message)

    def _pre_loop(self) -> None:
        assert self._req is not None
        self.disconnect = False
        self._queue_primary_thread = threading.Thread(
            target=self._queue_watcher,
            args=(self._queue_in, self._queue_out, "primary"),
        )

        self._queue_primary_thread.start()
        self._req.connect()
        self._logger.info("CoreService command operational")

    def _queue_watcher(
        self, input_queue: Queue[Any], output_queue: Queue[Any], label: str = "queue"
    ) -> None:
        assert self._merged_queue is not None
        while True:
            command: str = input_queue.get()
            self._merged_queue.put((command, output_queue, label))

    def _loop(self) -> None:
        assert self._merged_queue is not None
        assert self._queue_of_resp_queues is not None
        assert self._req is not None

        response = proto_cmd.Response()
        # Hang until a new command is received
        command, out_queue, label = self._merged_queue.get()
        assert isinstance(command, proto_cmd.Command)
        try:
            self._protobuf_to_log(command, "CMD {}")
            response_raw = self._req.send(command.SerializeToString(), timeout=10000)
        except Exception as e:
            self._logger.warning(
                f"Tried to send command {command} ({label}). Error {str(e)}"
            )
            return
        if response_raw is None:
            self._logger.warning(
                f"Tried to send command {command} ({label}). Socket error."
            )
            response.error.description = "Timeout"
        else:
            response.ParseFromString(response_raw)
            self._protobuf_to_log(response, "RSP {}")
        out_queue.put(response)
