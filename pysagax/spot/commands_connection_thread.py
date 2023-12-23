from __future__ import annotations

import multiprocessing
import queue
import threading
from typing import Optional

from pysagax.df.lena_core_service import BaseConnection


class CommandsConnectionThread(BaseConnection, threading.Thread):
    def __init__(
        self, status_queue: queue.Queue[str] | multiprocessing.Queue[str]
    ) -> None:
        BaseConnection.__init__(self)
        threading.Thread.__init__(self, daemon=True)
        self.incoming_buffer: bytearray = bytearray()
        self.status_text: str = ""
        self.incoming_messages_queue: queue.Queue[str] = queue.Queue()

        self.status_queue = status_queue

    def receive_on_socket(self, data: bytes) -> None:
        """
        When text is received on the command socket, display it in the console textbox.
        """
        self.incoming_buffer += data
        while b";" in self.incoming_buffer:
            idx = self.incoming_buffer.find(b";")
            self.incoming_messages_queue.put(self.incoming_buffer[0:idx].decode())
            self.incoming_buffer = self.incoming_buffer[idx + 1 :]

    def display_status(self, message: str) -> None:
        print(message)
        self.status_text = message
        self.status_queue.put(message)

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.disconnect = False
        self.run_socket()

    def send_command(self, cmd: str) -> Optional[str]:
        self.send_on_socket(cmd.encode())
        try:
            return self.incoming_messages_queue.get(block=True, timeout=30)
        except queue.Empty:
            return None
