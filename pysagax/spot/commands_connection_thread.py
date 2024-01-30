from __future__ import annotations

import multiprocessing
import queue
import threading
from typing import Optional

from pysagax.df.lena_core_service import BaseConnection


class CommandsConnectionThread(BaseConnection, threading.Thread):
    """
    Maintains a TCP socket for sending commands to the CoreService.
    """
    def __init__(
        self, status_queue: queue.Queue[str] | multiprocessing.Queue[str] | None
    ) -> None:
        """
        :param status_queue: a queue for async display of TCP/IP socket status
        """
        BaseConnection.__init__(self)
        threading.Thread.__init__(self, daemon=True)
        self.incoming_buffer: bytearray = bytearray()
        self.incoming_messages_queue: queue.Queue[str] = queue.Queue()
        self.status_text: str = ""
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

    def display_status_callback(self, message: str) -> None:
        """
        Is called by the base class to display the status of the TCP socket on the GUI.
        :param message: text to display on the GUI
        :return:
        """
        self.status_text = message
        if self.status_queue is not None:
            self.status_queue.put(message)

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.disconnect = False
        self.run_socket()

    def send_command(self, cmd: str, response_timeout: float = 30) -> Optional[str]:
        """
        Send a command on the commands socket and wait for a response
        :param cmd: CoreService command (see https://sagaxcommunications.atlassian.net/wiki/spaces/WBDF/pages/20676609)
        :param response_timeout: timeout for the response from the CoreService [seconds]
        :return: response from the CoreService (see page above), None on timeout
        """
        self.send_on_socket(cmd.encode())
        try:
            return self.incoming_messages_queue.get(block=True, timeout=response_timeout)
        except queue.Empty:
            return None
