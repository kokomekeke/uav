import queue
import socketserver
import socket
import threading
from typing import Callable, Iterable, Any, Mapping
from queue import Queue

import serial

from pysagax import open_aaronia_serial_dev

queues: list[Queue[bytes]] = []


class SerialHandlerThread(threading.Thread):
    def __init__(self, ser: serial.Serial) -> None:
        super().__init__(daemon=True)
        self.ser = ser

    def run(self) -> None:
        while True:
            try:
                line = self.ser.readline()
                print(line.decode().strip())
                global queues
                for q in queues:
                    q.put(line)
            except Exception as e:
                print(
                    "Compass sensor error",
                    f"Could not read from compass sensor, it might be disconnected. \n"
                    f"Please reconnect the sensor and then restart the python program. \n"
                    f"{str(e)}",
                )


class MyTCPHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self) -> None:
        global queues
        print(f"{self.client_address[0]} connected")
        """Handles a request ignoring dropped connections."""
        my_q: Queue[bytes] = Queue()
        global queues
        queues.append(my_q)
        try:
            while True:
                try:
                    line = my_q.get(block=True, timeout=1)
                    self.request.sendall(line)
                except queue.Empty:
                    print(f"No data to send for {self.client_address[0]}")
                    self.request.sendall(b"\n")

        except (socket.error, socket.timeout) as e:
            print(f"{self.client_address[0]} disconnencted")
            queues.remove(my_q)


if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 12938

    serial_thread = SerialHandlerThread(ser=open_aaronia_serial_dev())
    serial_thread.start()
    # Create the server, binding to localhost on port 9999
    with socketserver.TCPServer((HOST, PORT), MyTCPHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        server.serve_forever()
