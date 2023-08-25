#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 21/08/2023.
#
import datetime
import queue
import socketserver
import socket
import threading
from queue import Queue

import numpy as np

dfgmapserver_queues: list[Queue[bytes]] = []


class MyTCPHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self) -> None:
        print(f"{self.client_address[0]} connected")
        """Handles a request ignoring dropped connections."""
        my_q: Queue[bytes] = Queue()
        global dfgmapserver_queues
        dfgmapserver_queues.append(my_q)
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
            dfgmapserver_queues.remove(my_q)


class DFGMapServer(threading.Thread):
    def __init__(self) -> None:
        super().__init__()
        self.daemon = True
        self.total_packets: int = 0
        self.host = "0.0.0.0"
        self.port = 20000

        self.data_lat: int = 0
        self.data_lon: int = 0
        self.data_days: int = 0
        self.data_ms: int = 0
        self.data_freq: int = 0
        self.data_angle: int = 0

    def run(self) -> None:
        super().run()
        # Create the server, binding to localhost on port 9999
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer((self.host, self.port), MyTCPHandler) as server:
            # Activate the server; this will keep running until you
            # interrupt the program with Ctrl-C
            server.allow_reuse_port = True
            server.serve_forever()

    def count_clients(self) -> int:
        global dfgmapserver_queues
        return len(dfgmapserver_queues)

    def push_packet(self, packet: bytes) -> None:
        global dfgmapserver_queues
        self.total_packets += 1
        for q in dfgmapserver_queues:
            q.put(packet)

    def update_clients(self) -> None:
        self.push_packet(
            0x00000001.to_bytes(4, "little") + self.data_days.to_bytes(4, "little")
        )
        self.push_packet(
            0x00000000.to_bytes(4, "little") + self.data_ms.to_bytes(4, "little")
        )
        self.push_packet(
            0x00000003.to_bytes(4, "little")
            + self.data_lat.to_bytes(4, "little", signed=True)
        )
        self.push_packet(
            0x00000002.to_bytes(4, "little")
            + self.data_lon.to_bytes(4, "little", signed=True)
        )
        self.push_packet(
            self.data_freq.to_bytes(4, "little") + self.data_angle.to_bytes(4, "little")
        )

    def update_lat_lon(self, lat: float, lon: float) -> None:
        self.data_lat = int(lat * 1e6)
        self.data_lon = int(lon * 1e6)

    def update_timestamp(self) -> None:
        beginning = datetime.datetime(2000, 1, 1)
        current_time = datetime.datetime.utcnow()
        current_day = datetime.datetime(
            current_time.year, current_time.month, current_time.day
        )
        self.data_days = int((current_day - beginning).days)
        day_diff = current_time - current_day
        self.data_ms = int(
            day_diff.total_seconds() * 1000 + day_diff.microseconds / 1000
        )

    def update_angle(self, rad: float, freq: float) -> None:
        self.data_freq = int(freq)
        if rad < 0:
            rad += 2 * np.pi
        self.data_angle = int(rad * 180 * 1e6 / np.pi)
