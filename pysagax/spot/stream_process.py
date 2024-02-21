import multiprocessing
import multiprocessing.managers
import queue
import time

import typing
from typing import Optional
from pysagax.communication.broadcast import RX
import pysagax.message.data_pb2 as proto_data

from pysagax.util import MultiQueue


class StreamProcess(multiprocessing.Process):
    def __init__(
        self,
        connection_port: int,
        subscribed_groups: list[str],
        queues: MultiQueue,
        disconnect_value: multiprocessing.managers.ValueProxy[int],
        status_queue: queue.Queue,  # | multiprocessing.Queue,
    ):
        super().__init__(daemon=True, name="StreamProcess")
        self._connection_port = connection_port
        self._subscribed_groups = subscribed_groups
        self.queues = queues
        self._status_queue = status_queue

        self._do_disconnect_value = disconnect_value

        # timestamp for last received message:
        self._last_heartbeat_time: int = 0
        # connection deemed broken if nothing is received for this much time:
        self.heartbeat_timeout_ns: int = 10e9

    def connect(self) -> bool:
        self._connection = RX(
            port=self._connection_port, groups=self._subscribed_groups
        )
        self._display_connection_status_callback("Connecting...")
        self._connection.connect()
        self._display_connection_status_callback("Connected")
        self._last_heartbeat_time = time.time_ns()

    def disconnect(self) -> None:
        pass

    def is_disconnect(self) -> bool:
        if time.time_ns() - self._last_heartbeat_time > self.heartbeat_timeout_ns:
            self._display_connection_status_callback("Idle (timeout)")
            # self._display_connection_status_callback("Disconnected (timeout)")
            # return True #TODO: try to reconnect?

        try:  # (JIRA issue ALTS-150)
            do_disconnect = bool(self._do_disconnect_value.value)
        except:
            do_disconnect = False

        if do_disconnect:
            self._display_connection_status_callback("Disconnected")
            return True
        return False

    def run(self) -> None:
        self.connect()
        self.loop()
        self.disconnect()

    def loop(self) -> None:
        while not self.is_disconnect():
            raw_data = self._connection.recv(
                timeout=200
            )  # raw_data: either None or [packe, type]
            if raw_data is None:  # recv timeout
                continue
            self._last_heartbeat_time = time.time_ns()
            if raw_data[1] != "Measurement":
                print(f"Handling stream packet type {raw_data[1]} is not implemented")
                continue
            data = proto_data.Measurement()
            data.ParseFromString(raw_data[0])
            self.queues.put(data)

    def _display_connection_status_callback(self, message: str) -> None:
        self._status_queue.put(message)
