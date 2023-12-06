#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 08.11.2023.
#
import math
import os
import queue
import socket
import socketserver
import threading
import typing
from datetime import datetime
from queue import Queue

import serial
from pymavlink import mavutil

queues: list[Queue[bytes]] = []


class MavlinkHandlerThread(threading.Thread):
    def __init__(self, mavlink: typing.Any) -> None:
        super().__init__(daemon=True)
        self.mavlink = mavlink

    def send_line(self, line: str) -> None:
        char_check = 0
        for char in line.encode():
            char_check ^= char
        line_ext = f"${line}*{char_check:02X}"
        global queues
        for q in queues:
            q.put(line_ext.encode())

    def run(self) -> None:
        last_time_string_att = "000000"
        last_time_string_imu = "000000"
        last_time_string_gps = "000000"
        time_string = "000000"
        time_sub_att = 0
        time_sub_imu = 0
        time_sub_gps = 0
        while True:
            try:
                msg = self.mavlink.recv_msg()
                if msg is not None:
                    msg_type = msg.get_type()
                    msg_data = msg.to_dict()
                    time_string = datetime.now().strftime("%H%M%S")
                    if "ATTITUDE" == msg_type:
                        roll = getattr(msg, "roll")
                        pitch = getattr(msg, "pitch")
                        yaw = getattr(msg, "yaw")
                        if last_time_string_att == time_string and time_sub_att < 99:
                            time_sub_att += 1
                        else:
                            time_sub_att = 0

                        last_time_string_att = time_string
                        self.send_line(
                            f"PAAG,DATA,A,{time_string}.{time_sub_att:02d},{yaw},{pitch},{roll},A"
                        )
                    if "SCALED_IMU2" == msg_type:
                        xmag = getattr(msg, "xmag")
                        ymag = getattr(msg, "ymag")
                        zmag = getattr(msg, "zmag")

                        xacc = getattr(msg, "xacc")
                        yacc = getattr(msg, "yacc")
                        zacc = getattr(msg, "zacc")

                        xgyro = getattr(msg, "xgyro")
                        ygyro = getattr(msg, "ygyro")
                        zgyro = getattr(msg, "zgyro")
                        if last_time_string_imu == time_string and time_sub_imu < 99:
                            time_sub_imu += 1
                        else:
                            time_sub_imu = 0

                        last_time_string_imu = time_string
                        self.send_line(
                            f"PAAG,DATA,C,{time_string}.{time_sub_imu:02d},{xmag},{ymag},{zmag},A"
                        )
                        self.send_line(
                            f"PAAG,DATA,G,{time_string}.{time_sub_imu:02d},{xgyro},{ygyro},{zgyro},A"
                        )
                        self.send_line(
                            f"PAAG,DATA,T,{time_string}.{time_sub_imu:02d},{xacc},{yacc},{zacc},A"
                        )

                    if "GLOBAL_POSITION_INT" in msg_type:
                        lat = getattr(msg, "lat")
                        lon = getattr(msg, "lon")
                        alt = getattr(msg, "alt")

                        lat_deg = int(math.fabs(lat / 1e7))
                        lat_min = (math.fabs(lat / 1e7) - lat_deg) * 60
                        lat_hem = "N" if lat >= 0 else "S"
                        lon_deg = int(math.fabs(lon / 1e7))
                        lon_min = (math.fabs(lon / 1e7) - lon_deg) * 60
                        lon_hem = "E" if lon >= 0 else "W"
                        relative_alt = getattr(msg, "relative_alt")
                        if last_time_string_gps == time_string and time_sub_gps < 99:
                            time_sub_gps += 1
                        else:
                            time_sub_gps = 0

                        last_time_string_gps = time_string
                        self.send_line(
                            f"GPGGA,{time_string}.{time_sub_gps:02d},{lat_deg:02d}{lat_min:08.5f},{lat_hem},{lon_deg:02d}{lon_min:08.5f},{lon_hem},1,05,0.0,0.0,M,0.0,M,,"
                        )

            except TypeError as e:
                pass
                # print(f"nem baj: {repr(e)}")
                # os._exit(1)


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
                    print(line.decode())
                    self.request.sendall(b"\n")
                except queue.Empty:
                    print(f"No data to send for {self.client_address[0]}")
                    self.request.sendall(b"\n")

        except (socket.error, socket.timeout) as e:
            print(f"{self.client_address[0]} disconnencted")
            queues.remove(my_q)


def main() -> None:
    HOST, PORT = "0.0.0.0", 12938
    UDP_HOST = "127.0.0.1"  # '10.223.2.65'
    UDP_PORT = 14550

    mavlink_thread = MavlinkHandlerThread(
        mavutil.mavlink_connection(f"udpin:{UDP_HOST}:{UDP_PORT}")
    )
    mavlink_thread.start()
    socketserver.TCPServer.allow_reuse_address = True
    # Create the server, binding to localhost on port 9999
    with socketserver.TCPServer((HOST, PORT), MyTCPHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        server.serve_forever()


if __name__ == "__main__":
    main()
