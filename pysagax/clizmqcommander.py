#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 28/02/2024.
#
from __future__ import annotations
import argparse
import time
from humanfriendly.terminal import ansi_wrap


from google.protobuf import json_format
import pysagax.message.command_pb2 as proto
import queue
import threading
from typing import Any, Callable, Optional

from pysagax.communication.req_rep_tcp import REQ

parser = argparse.ArgumentParser(description="CLI ZMQ commander parameters")
parser.add_argument("address")
args = parser.parse_args()


class ZMQConnectionThread(threading.Thread):
    def __init__(self, address: str = "127.0.0.1") -> None:
        super().__init__(daemon=True)

        self.address = address

        port_s = 5556
        print(ansi_wrap(text=f"Connecting to {address}:{port_s}", color="blue"))
        # Define up- and downstream channels
        self._zmq = REQ(address_server=address, port_server=port_s)
        self.disconnect: bool = False
        self.connect_callback: Optional[Callable[[], None]] = None
        """
        This function handle is called when the socket is initiating connection.
        """

        self.connected_callback: Optional[Callable[[], None]] = None
        """
        This function handle is called when the socket is initiating connection.
        """

        self.disconnect_callback: Optional[Callable[[], None]] = None
        """
        This function handle is called when the socket is disconnected.
        """

        self.connected: bool = False
        """
        Flag that indicates if the socket is connected.
        """
        self.send_queue = queue.Queue()

    def connect(self):
        """Connect and bind up- and downstream sockets"""

        if self.connect_callback is not None:
            self.connect_callback()
        self._zmq.connect()
        self.display_status_callback("ZMQ Connected")
        self.connected = True
        if self.connected_callback is not None:
            self.connected_callback()

    def display_status_callback(self, message: str) -> None:
        try:
            print(ansi_wrap(text=message, color="blue"))
        except RuntimeError:
            pass  # it might happen when closing the window

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.connect()
        while not self.disconnect:
            try:
                command = self.send_queue.get(timeout=2)
                raw_response = self._zmq.send(
                    command.SerializeToString(), timeout=20000
                )
                if raw_response is not None:
                    response = proto.Response()
                    response.ParseFromString(raw_response)

                    to_print = json_format.MessageToJson(response)
                    print(ansi_wrap(text="=== Response: ", color="red", bold=True))
                    print(to_print)
                    print()

                    print(ansi_wrap(text="=== Command: ", color="red", bold=True))
                else:
                    print(ansi_wrap(text="No response", color="blue"))
            except queue.Empty:
                pass
            except TimeoutError:
                self.display_status_callback("Connection timed out")
                break
            except ConnectionError:
                self.display_status_callback("Connection broken")
                break
        self.connected = False
        self.display_status_callback("Disconnected")
        if self.disconnect_callback is not None:
            self.disconnect_callback()


def main() -> None:
    global args

    client = ZMQConnectionThread(address=args.address)
    client.start()
    buf = ""
    while not client.connected:
        print(ansi_wrap(text="...", color="blue"))
        time.sleep(0.5)

    print(ansi_wrap(text="=== Command: ", color="red", bold=True))
    while client.connected:
        try:
            inp = input()
        except EOFError:
            return
        buf += f"\n{inp}"
        if not inp:
            if buf:
                try:
                    command = json_format.Parse(buf.strip(), proto.Command())
                    client.send_queue.put(command)
                    buf = ""
                    print(ansi_wrap(text="...", color="blue"))
                except json_format.ParseError as e:
                    print(f"{e}")
            else:
                break


if __name__ == "__main__":
    main()
