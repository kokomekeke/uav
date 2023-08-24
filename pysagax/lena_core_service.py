#
# Created by aron.szabo@sagaxcommunications.com on 15/05/2022.
#
from __future__ import annotations

import multiprocessing
import socket
import struct
import threading
import time
from typing import Callable, Optional

import numpy as np
import numpy.typing as npt


class CoreServicePacket:
    """
    Represents one packet received from the Core Service.
    """

    def __init__(self) -> None:
        self.stream_id: int = 0
        self.packet_type: int = 0
        self.end_of_file: bool = False
        self.center_frequency: float = 0
        self.span: float = 0.0
        self.iq_rate: float = 0.0
        self.sample_index: int = 0
        self.packet_index: int = 0
        self.bin_count: int = 0
        self.magnitude_spectrum: npt.NDArray[np.float64] = np.zeros([1])
        self.azimuth_spectrum: npt.NDArray[np.float64] = np.zeros([1])
        self.elevation_spectrum: npt.NDArray[np.float64] = np.zeros([1])
        self.time_ns: int = 0
        self.roi_level: float = 0.0
        self.roi_azimuth: float = 0.0
        self.roi_elevation: float = 0.0
        self.title: str = ""
        self.contents: bytes = b""

    def __str__(self) -> str:
        return {
            0: f"#{self.packet_index} Unknown",
            1: f"#{self.packet_index} Spectrum (C: {self.center_frequency/1e6:.3f}M, IQ: {self.iq_rate/1e6:.2f}M, {self.bin_count} bins)",
            2: f"#{self.packet_index} EOF",
            3: (
                f"#{self.packet_index} ROI peak {self.center_frequency/1e6:.3f}M, {self.roi_level:.1f}dB "
                f"Az: {self.roi_azimuth:.2f} ({self.roi_azimuth / np.pi * 180:.2f}deg), "
                f"El: {self.roi_elevation:.2f} ({self.roi_elevation / np.pi * 180:.2f}deg) "
            ),
            4: f"#{self.packet_index} ROI lack of signal",
            6: f"#{self.packet_index} Debug {self.title} {'' if len(self.contents)>128 else self.contents.decode()}",
        }[self.packet_type]


class BaseConnection:
    """
    Base class for both the Command and Stream connections.
    """

    def __init__(self) -> None:
        super().__init__()
        # Thread is daemon, it will quit on closing the program.
        self.daemon = True

        self.host_port = ""
        """
        Host and port in <address>:<tcp port> format.
        """

        self.client_socket: Optional[socket.socket] = None
        """
        Python client socket object 
        """

        self.disconnect: bool = False
        """
        When the disconnect flag is set, the thread loop will quit on the next iteration.
        """

        self.connected: bool = False
        """
        Flag that indicates if the socket is connected.
        """

        self.connect_action: Optional[Callable[[], None]] = None
        """
        This function handle is called when the socket is connected.
        """

        self.disconnect_action: Optional[Callable[[], None]] = None
        """
        This function handle is called when the socket is disconnected.
        """

        self.buf_size: int = 2048
        """
        This buffer size will be read at once from the TCP socket.
        """

    def display_status(self, message: str) -> None:
        """
        Display a status message (on the GUI status bar)
        """
        pass

    def is_disconnect(self) -> bool:
        """
        Returns: if the socket should manually disconnect
        """
        return self.disconnect

    def run_socket(self) -> None:
        """
        General implementation of socket handling for both the stream and the command sockets.
        """
        if not self.host_port:
            return
        host_port_split = self.host_port.split(":")
        host, port = (host_port_split[0], host_port_split[1])
        try:
            if self.connect_action is not None:
                self.connect_action()
            self.display_status("Connecting...")
            self.client_socket = socket.socket()  # instantiate
            self.client_socket.settimeout(1.0)
            self.client_socket.connect((host, int(port)))  # connect to the server
            self.connected = True
            self.display_status("Connected")
            while True:
                try:
                    if self.is_disconnect():
                        self.display_status("Disconnected")
                        break
                    data = self.client_socket.recv(self.buf_size)  # receive response
                    if not data:  # If the pipe is broken, data will be empty string
                        self.display_status("Disconnected")
                        break
                    self.receive_on_socket(data)
                except TimeoutError:
                    pass
        except TimeoutError:
            self.display_status("Connection timed out")
            pass
        except ConnectionError:
            self.display_status("Connection broken")
            pass
        except OSError as e:
            self.display_status(f"Connection error: {e}")
            pass
        self.connected = False
        if self.client_socket:
            self.client_socket.close()  # close the connection
        if self.disconnect_action is not None:
            self.disconnect_action()

    def receive_on_socket(self, data: bytes) -> None:
        """
        When data is received on the socket, this function will handle the data.
        """
        pass


class StreamConnectionProcess(BaseConnection, multiprocessing.Process):
    """
    This thread (process) will handle the stream socket and place the incoming samples in a numpy structure.
    The purpose of moving the stream TCP/IP connection and preprocessing of the packets to a separate
    multiprocessing process is to ensure there are no delays on the reception, and to be independent of the GUI
    """

    def __init__(
        self,
        packets_queue: multiprocessing.Queue[CoreServicePacket],
        disconnect_value: multiprocessing.managers.ValueProxy[int],
        status_value: multiprocessing.Queue[str],
    ):
        super(StreamConnectionProcess, self).__init__()

        self.counter_packet_ratio: float = 0
        """
        Used to count number of received packets in a uniform period of time. Ratio is the result of that calculation.
        """

        self.counter_ns: int = time.time_ns()
        """
        Helper variable to packet ratio. Counter_ns is a nanosecond timestamp 
        that marks the start of the current counting block.
        """

        self.counter_packet_index: int = 0
        """
        Helper variable to packet ratio. This is the counter variable.
        """

        self.counter_block_size_parameter: int = 100000000
        """
        This parameter sets the counting window of the packet ratio calculation.
        """

        self.mp_status: multiprocessing.Queue[str] = status_value
        """
        Status message queue for multiprocessing process
        """

        self.mp_disconnect: multiprocessing.managers.ValueProxy[int] = disconnect_value
        """
        Disconnect signal for multiprocessing process
        """

        self.mp_queue: multiprocessing.Queue[CoreServicePacket] = packets_queue
        """
        CS packet queue for multiprocessing process
        """

        self.buffer = bytearray()
        """
        Binary packet data buffer
        """

        self.packet_count = 0
        """
        Overall packet count
        """

        self.buf_size = 131072  # 65536
        """
        This buffer size will be read at once from the TCP socket.
        """

    def run(self) -> None:
        """
        Entry point of the stream collecting process.
        """
        self.run_socket()
        self.mp_status.put("END")

    def is_disconnect(self) -> bool:
        """
        Returns: if the socket should manually disconnect
        """
        assert self.mp_disconnect is not None
        return bool(self.mp_disconnect.value)

    def display_status(self, message: str) -> None:
        """
        Display a status message (on the GUI status bar)
        """
        assert self.mp_status
        self.mp_status.put(message)

    def insert_packet(self, cs_packet: CoreServicePacket) -> None:
        self.packet_count += 1
        cs_packet.packet_index = self.packet_count
        self.mp_queue.put(cs_packet)
        while self.counter_ns + self.counter_block_size_parameter <= time.time_ns():
            self.counter_packet_ratio = self.counter_packet_index * (
                1e9 / self.counter_block_size_parameter
            )
            self.counter_packet_index = 0
            self.counter_ns += self.counter_block_size_parameter
        self.counter_packet_index += 1
        try:
            self.display_status(
                f"Packet {cs_packet.packet_index} - Stream {cs_packet.stream_id}, "
                f"index {cs_packet.sample_index} , speed: {self.counter_packet_ratio} packets/sec, "
                f"queue count on insert: {self.mp_queue.qsize()}"
            )
        except (
            NotImplementedError
        ):  # multiprocessing.Queue.qsize() not implemented on Mac OS X
            self.display_status(
                f"Packet {cs_packet.packet_index} - Stream {cs_packet.stream_id}, "
                f"index {cs_packet.sample_index}"
            )

    def receive_on_socket(self, data: bytes) -> None:
        """
        When data is received on the socket, this function will construct a packet object from the binary data.
        """
        assert self.mp_queue
        self.buffer += bytearray(data)
        while len(self.buffer) >= 8:  # packet header is 28 bytes
            cs_packet = CoreServicePacket()
            cs_packet.stream_id = int.from_bytes(self.buffer[0:4], "little")
            cs_packet.packet_type = int.from_bytes(self.buffer[4:8], "little")
            cs_packet.time_ns = time.time_ns()

            if len(self.buffer) >= 28 and cs_packet.packet_type == 1:
                cs_packet.center_frequency = struct.unpack("f", self.buffer[8:12])[0]
                cs_packet.iq_rate = struct.unpack("f", self.buffer[12:16])[0]
                cs_packet.sample_index = int.from_bytes(self.buffer[16:24], "little")
                cs_packet.bin_count = int.from_bytes(self.buffer[24:28], "little")
                packet_size = 3 * 4 * cs_packet.bin_count + 28
                if (
                    len(self.buffer) >= packet_size
                ):  # we got the entire packet in buffer
                    cs_packet.magnitude_spectrum = np.asarray(
                        struct.unpack(
                            f"{cs_packet.bin_count}f",
                            self.buffer[28 : 28 + cs_packet.bin_count * 4],
                        )
                    )  # type: ignore
                    cs_packet.azimuth_spectrum = np.asarray(
                        struct.unpack(
                            f"{cs_packet.bin_count}f",
                            self.buffer[
                                (28 + cs_packet.bin_count * 4) : (
                                    28 + cs_packet.bin_count * 4 * 2
                                )
                            ],
                        )
                    )  # type: ignore
                    cs_packet.elevation_spectrum = np.asarray(
                        struct.unpack(
                            f"{cs_packet.bin_count}f",
                            self.buffer[
                                (28 + cs_packet.bin_count * 4 * 2) : (
                                    28 + cs_packet.bin_count * 4 * 3
                                )
                            ],
                        )
                    )  # type: ignore
                    self.insert_packet(cs_packet)
                    self.buffer = self.buffer[packet_size:]  # drop packet from buffer
                else:
                    break  # wait until next tcp read
            elif cs_packet.packet_type == 2:  # end of file
                cs_packet.end_of_file = True
                self.insert_packet(cs_packet)
                self.buffer = self.buffer[8:]
            elif len(self.buffer) >= 28 and cs_packet.packet_type == 3:  # roi result
                cs_packet.center_frequency = struct.unpack("f", self.buffer[8:12])[0]
                cs_packet.span = struct.unpack("f", self.buffer[12:16])[0]
                cs_packet.roi_level = struct.unpack("f", self.buffer[16:20])[0]
                cs_packet.roi_azimuth = struct.unpack("f", self.buffer[20:24])[0]
                cs_packet.roi_elevation = struct.unpack("f", self.buffer[24:28])[0]
                self.insert_packet(cs_packet)
                self.buffer = self.buffer[28:]  # drop packet from buffer
            elif cs_packet.packet_type == 4:  # roi lack of signal
                self.insert_packet(cs_packet)
                self.buffer = self.buffer[8:]
            elif len(self.buffer) >= 24 and cs_packet.packet_type == 6:  # debug
                category_size = int.from_bytes(self.buffer[12:16], "little")
                data_size = int.from_bytes(self.buffer[16:24], "little")
                if len(self.buffer) >= 24 + category_size + data_size:
                    cs_packet.title = self.buffer[24 : 24 + category_size].decode()
                    cs_packet.contents = self.buffer[
                        (24 + category_size) : (24 + category_size + data_size)
                    ]
                    self.insert_packet(cs_packet)
                    self.buffer = self.buffer[(24 + category_size + data_size) :]
                else:
                    break
            elif cs_packet.packet_type > 6:
                self.buffer = self.buffer[4:]
                self.display_status(
                    f"Stream {cs_packet.stream_id}, "
                    f"Unsupported packet type {cs_packet.packet_type}"
                )
            else:
                break  # no whole packet in the buffer, or unsupported data


class StreamProcessingThread(threading.Thread):
    """
    This thread is responsible for handling the multiprocessing stream process and for displaying the stream contents
    on the matplotlib plots
    """

    def __init__(self) -> None:
        super().__init__()
