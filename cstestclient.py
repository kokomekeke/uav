#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 21/12/2022.
#
from __future__ import annotations

import argparse
import math
import multiprocessing
import os
import queue
import re
import socket
import struct
import threading
import time
import tkinter
import typing
from datetime import datetime
from time import sleep
from typing import Any, Callable, Optional

import matplotlib.cm
import numpy as np
import numpy.typing as npt
import serial
from matplotlib import pyplot
from matplotlib.animation import FuncAnimation  # type: ignore
from matplotlib.backend_bases import KeyEvent, key_press_handler  # type: ignore
from matplotlib.backends.backend_tkagg import (  # type: ignore
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

parser = argparse.ArgumentParser(description="CS Test client parameters")
parser.add_argument(
    "--bin",
    metavar="N",
    type=int,
    default=0,
    help="maximum displayed bin count (set if experiencing performance issues) 0=disable decimation",
)
parser.add_argument(
    "--wf",
    metavar="N",
    type=int,
    default=200,
    help="maximum packets displayed on waterfall (set if experiencing performance issues)",
)
parser.add_argument(
    "--fps",
    metavar="N",
    type=int,
    default=30,
    help="matplotlib display framerate",
)
parser.add_argument(
    "--disp", default=True, action="store_true", help="turn on matplotlib display"
)
parser.add_argument(
    "--no-disp", dest="disp", action="store_false", help="turn off matplotlib display"
)
parser.add_argument(
    "--phases-roi-wf",
    dest="phases_roi_wf",
    default=False,
    action="store_true",
    help="display phases roi waterfall",
)
parser.add_argument(
    "--roi-wf",
    dest="roi_wf",
    default=False,
    action="store_true",
    help="display roi waterfall",
)
parser.add_argument(
    "--sensor-dev",
    dest="sensor_dev",
    metavar="N",
    type=str,
    help="sensor device",
)
args = parser.parse_args()

roi_data = np.empty([0, 2])
compass_data = np.empty([0, 3])


class CompassSensor(threading.Thread):
    def __init__(self) -> None:
        super().__init__()
        global args
        self.daemon = True
        self.ser = serial.Serial()
        self.ser.port = args.sensor_dev  # "/dev/rfcomm2"
        # If it breaks try the below
        # self.serConf() # Uncomment lines here till it works

        self.ser.baudrate = 9600
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 50  # Non-Block reading
        self.ser.xonxoff = False  # Disable Software Flow Control
        self.ser.rtscts = False  # Disable (RTS/CTS) flow Control
        self.ser.dsrdtr = False  # Disable (DSR/DTR) flow Control
        # self.ser.writeTimeout = 2
        self.ser.open()
        # self.ser.flushInput()
        # self.ser.flushOutput()

        self.sensor: float = 0.0
        self.compass = np.array([0.0, 0.0, 0.0])

        self.addr = None

    def run(self) -> None:
        pattern = re.compile(
            r"\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*"
        )
        while True:
            line = self.ser.readline()
            tokens = pattern.match(line.decode())
            if tokens is None:
                continue
            try:
                self.compass = np.array(
                    [
                        float(tokens.group(4)),
                        float(tokens.group(5)),
                        float(tokens.group(6)),
                    ]
                )
                print(self.compass)
                self.sensor = math.atan2(self.compass[0], self.compass[1])
            except ValueError:
                pass

    def close(self) -> None:
        self.ser.close()


compass: Optional[CompassSensor] = None


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
            1: f"#{self.packet_index} Spectrum (C: {self.center_frequency / 1e6:.3f}M, IQ: {self.iq_rate / 1e6:.2f}M, {self.bin_count} bins)",
            2: f"#{self.packet_index} EOF",
            3: (
                f"#{self.packet_index} ROI peak {self.center_frequency / 1e6:.3f}M, "
                f"Az: {self.roi_azimuth:.2f} ({self.roi_azimuth / np.pi * 180:.2f}deg), "
                f"El: {self.roi_elevation:.2f} ({self.roi_elevation / np.pi * 180:.2f}deg) "
            ),
            4: f"#{self.packet_index} ROI lack of signal",
            6: f"#{self.packet_index} Debug {self.title}",
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


class CommandsConnectionThread(BaseConnection, threading.Thread):
    def __init__(self) -> None:
        super(CommandsConnectionThread, self).__init__()
        self.console_textarea_ref: Optional[tkinter.Text] = None
        """
        Reference of the commands connection console textarea on the main window
        """

        self.status_label_ref: Optional[tkinter.Label] = None
        """
        Reference of the status label on the main window
        """

    def receive_on_socket(self, data: bytes) -> None:
        """
        When text is received on the command socket, display it in the console textbox.
        """
        assert self.console_textarea_ref
        self.console_textarea_ref.configure(
            state="normal"
        )  # Textarea has to be unlocked to enable modification
        self.console_textarea_ref.insert(tkinter.END, "\n")
        self.console_textarea_ref.insert(tkinter.END, data.decode())
        self.console_textarea_ref.see(tkinter.END)  # Scroll to the bottom
        self.console_textarea_ref.configure(state="disabled")  # Block user editing

    def display_status(self, message: str) -> None:
        assert self.status_label_ref
        try:
            self.status_label_ref.config(text=message)
        except RuntimeError:
            pass  # it might happen when closing the window

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.disconnect = False
        self.run_socket()


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

        self.counter_block_size_parameter: int = 2000000000
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
        except NotImplementedError:  # multiprocessing.Queue.qsize() not implemented on Mac OS X
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
                    )
                    cs_packet.azimuth_spectrum = np.asarray(
                        struct.unpack(
                            f"{cs_packet.bin_count}f",
                            self.buffer[
                                (28 + cs_packet.bin_count * 4) : (
                                    28 + cs_packet.bin_count * 4 * 2
                                )
                            ],
                        )
                    )
                    cs_packet.elevation_spectrum = np.asarray(
                        struct.unpack(
                            f"{cs_packet.bin_count}f",
                            self.buffer[
                                (28 + cs_packet.bin_count * 4 * 2) : (
                                    28 + cs_packet.bin_count * 4 * 3
                                )
                            ],
                        )
                    )
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


class StreamDisplayThread(threading.Thread):
    """
    This thread is responsible for handling the multiprocessing stream process and for displaying the stream contents
    on the matplotlib plots
    """

    def __init__(self) -> None:
        super().__init__()

        self.recreate_canvas_action: Optional[Callable[[], None]] = None
        """
        Action that recreates plot canvas
        """

        global args
        self.waterfall_size = args.wf
        """
        Amount of spectrum lines to be displayed on the waterfall diagram.
        """

        self.fig_ref: Optional[pyplot.Figure] = None
        """
        Reference to the matplotlib figure.
        """

        self.waterfall = np.ones([1, 1])
        """
        Magnitude waterfall data (numpy matrix)
        """

        self.azimuth_spectrum = np.ones([1])
        """
        Azimuth spectrum data [rad] (numpy vector)
        """

        self.elevation_spectrum = np.ones([1])
        """
        Elevation spectrum data [rad] (numpy vector)
        """

        self.roi_waterfall = np.ones([1, 1])
        """
        ROI waterfall data (Rows: time, Cols: [Az, El])
        """

        self.roi_phases = np.ones([1, 1])
        """
        ROI waterfall data (Rows: time, Cols: [ch1-ch0, ch2-ch0, ch3-ch0])
        """

        self.roi_enabled: bool = False
        """
        ROI is enabled
        """

        self.roi_bin: int = 0
        """
        FFT bin position of ROI result
        """

        self.roi_azimuth: float = 0
        """
        Azimuth [rad] of ROI result
        """

        self.roi_elevation: float = 0
        """
        Elevation [rad] of ROI result
        """

        self.magnitude_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the magnitude plot
        """

        self.azimuth_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the azimuth plot
        """

        self.elevation_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the elevation plot
        """

        self.roi_waterfall_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the ROI plot
        """

        self.magnitude_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the magnitude plot
        """

        self.azimuth_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the azimuth plot
        """

        self.azimuth_roi_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the azimuth plot
        """

        self.elevation_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the elevation plot
        """

        self.elevation_roi_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the elevation plot
        """

        self.roi_waterfall_azimuth_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the ROI waterfall azimuth
        """

        self.roi_waterfall_elevation_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the ROI waterfall elevation
        """

        self.roi_waterfall_compass_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the ROI compass
        """

        self.roi_waterfall_phase1_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the ROI waterfall Phase 1
        """

        self.roi_waterfall_phase2_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the ROI waterfall Phase 1
        """

        self.roi_waterfall_phase3_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object for the ROI waterfall Phase 1
        """

        self.animation: Optional[matplotlib.animation.FuncAnimation] = None
        """
        Matplotlib FuncAnimation object for animating the graphs
        """

        self.animation_started: bool = False
        """
        Indicates whether the animation and plot objects have been created
        """

        self._center_frequency: float = 0
        """
        Center frequency of the last burst
        """

        self._iq_rate: float = 0
        """
        Iq rate of the last burst
        """

        self._bin_count: int = 0
        """
        Bin count of the last burst
        """

        self.status_label_ref: Optional[tkinter.Label] = None
        """
        Reference of the status label on the main window
        """

        self.packets_lb_ref: Optional[tkinter.Listbox] = None
        """
        Reference of the packets listbox on the main window
        """

        self.disconnect: bool = False
        """
        When the disconnect flag is set, the thread loop will quit on the next iteration.
        """

        self.host_port = ""
        """
        Host and port in <address>:<tcp port> format.
        """

        manager = multiprocessing.get_context("spawn").Manager()
        self.disconnect_value = manager.Value("i", 0)
        """
        Setting the '1' value of the disconnect_value multiprocessing variable will end the multiprocessing task on the
        next iteration.
        """

    def run(self) -> None:
        """
        Entry point of the data handling thread
        """

        global args
        status_queue: multiprocessing.Queue[str] = multiprocessing.Queue()
        """
        The string elements of the status queue are the messages to be displayed on the GUI status bar
        """

        packet_string_queue: queue.Queue[str] = queue.Queue()

        def status_watcher() -> None:
            """
            Entry point of the watcher thread
            """
            assert self.status_label_ref is not None
            assert self.packets_lb_ref is not None
            while True:
                try:
                    terminate = False
                    self.disconnect_value.value = self.disconnect
                    disp_message = ""
                    while not status_queue.empty():
                        message = status_queue.get(
                            timeout=0.2
                        )  # get status message from stream process
                        if message == "END":
                            terminate = True
                        else:
                            disp_message = message
                    if (
                        disp_message != ""
                    ):  # only send the last message to UI (UI calls are slow)
                        self.status_label_ref.config(text=disp_message)  # slow UI call
                    list_items: list[str] = []
                    while not packet_string_queue.empty():
                        list_items.append(packet_string_queue.get())
                    self.packets_lb_ref.insert(tkinter.END, *list_items)  # slow UI call
                    self.packets_lb_ref.delete(
                        0, self.packets_lb_ref.size() - 1000
                    )  # slow UI call
                    self.packets_lb_ref.see(tkinter.END)  # slow UI call
                    if terminate:
                        return
                except queue.Empty:
                    pass
                except BrokenPipeError:
                    return
                except RuntimeError:
                    return  # it might happen on the UI when closing the window

        # The purpose of the watcher thread is to take the status messages from the multiprocessing process and display
        # them on the GUI, and to forward the disconnect signal to the process if the "Disconnect" button is clicked.
        watcher_thread = threading.Thread(target=status_watcher, daemon=True)
        watcher_thread.start()

        packets_queue: multiprocessing.Queue[
            CoreServicePacket
        ] = multiprocessing.Queue()
        """
        This queue will transfer the processed packets from the stream process to the main (GUI) process
        """

        stream_process = StreamConnectionProcess(
            packets_queue, self.disconnect_value, status_queue
        )

        stream_process.host_port = self.host_port
        stream_process.start()

        debug_phases: list[float] = [0.0, 0.0, 0.0]
        # The code below will handle the preprocessed packets from the stream process
        assert self.status_label_ref
        while True:
            if self.disconnect:
                break
            try:
                packet: CoreServicePacket = packets_queue.get(
                    timeout=0.5
                )  # get a packet from the stream process
            except queue.Empty:
                continue
            ts = datetime.fromtimestamp(packet.time_ns / 1e9, tz=None)
            packet_string_queue.put(
                f"[{packet.stream_id}] {ts.strftime('%H:%M:%S')}.{int((packet.time_ns % 1e9) / 1e6):03d} - "
                f"{str(packet)}",
            )  # handle UI in a separate thread, because UI calls are slow
            if packet.end_of_file:
                continue  # no animation for EOF packet
            if packet.packet_type == 3:
                self.roi_enabled = True
                if self._iq_rate == 0:
                    self.roi_bin = 0
                else:
                    self.roi_bin = int(
                        (packet.center_frequency - self._center_frequency)
                        * (self.azimuth_spectrum.size / self._iq_rate)
                        + self.azimuth_spectrum.size / 2
                    )
                self.roi_azimuth = packet.roi_azimuth
                self.roi_elevation = packet.roi_elevation
            if packet.packet_type == 4:
                self.roi_enabled = False
            if packet.packet_type == 6:
                spec_len = self._bin_count * 4
                ch1_spectrum: npt.NDArray[np.float32] = np.asarray(
                    struct.unpack(
                        f"{self._bin_count}f",
                        packet.contents[0:spec_len],
                    )
                )
                ch2_spectrum: npt.NDArray[np.float32] = np.asarray(
                    struct.unpack(
                        f"{self._bin_count}f",
                        packet.contents[spec_len : spec_len * 2],
                    )
                )
                ch3_spectrum: npt.NDArray[np.float32] = np.asarray(
                    struct.unpack(
                        f"{self._bin_count}f",
                        packet.contents[spec_len * 2 : spec_len * 3],
                    )
                )
                if self.roi_bin < self._bin_count:
                    debug_phases = [
                        ch1_spectrum[self.roi_bin],
                        ch2_spectrum[self.roi_bin],
                        ch3_spectrum[self.roi_bin],
                    ]
            if packet.packet_type > 2:
                continue
            if packet.bin_count == 0:
                continue
            if not args.disp:
                continue
            magnitude = packet.magnitude_spectrum
            azimuth = packet.azimuth_spectrum
            elevation = packet.elevation_spectrum

            if (
                args.bin > 0
            ):  # args.bin is the maximum bin count the display can handle. 0 if disabled
                # Max bin count the matplotlib frontend can manage to display smoothly.
                # Can be adjusted to PC configuration.
                decimate = 1
                while packet.bin_count / decimate > args.bin:
                    decimate *= 2
                if decimate > 1:
                    magnitude = magnitude[:-1:decimate]
                    azimuth = azimuth[:-1:decimate]
                    elevation = elevation[:-1:decimate]
            if (
                not self.animation_started  # start matplotlib animation if it has not started yet
                or magnitude.size
                != self.waterfall.shape[1]  # or restart if the dimensions change
                or packet.center_frequency
                != self._center_frequency  # or restart if the axes change
                or packet.iq_rate != self._iq_rate
            ):
                # Animation can be created, because at this point we know bin count and other properties
                # Also restart when bin count or any other parameter has changed
                self.create_anim(
                    bin_count=packet.bin_count,
                    data_bin_count=magnitude.size,
                    center_freq=packet.center_frequency,
                    iq_rate=packet.iq_rate,
                    vmin=float(np.min(magnitude)),
                    vmax=0,  # float(np.max(magnitude)),
                )  # type: ignore
                self._iq_rate = packet.iq_rate
                self._bin_count = packet.bin_count
                self._center_frequency = packet.center_frequency
                self.animation_started = True

            self.azimuth_spectrum = azimuth
            self.elevation_spectrum = elevation
            # FIFO on the waterfall data structure
            self.waterfall = np.append(
                self.waterfall[-self.waterfall_size + 1 :, :],
                np.array([magnitude]),
                axis=0,
            )
            if args.roi_wf:
                sensor: Optional[float] = None
                global compass
                if compass is not None:
                    sensor = compass.sensor
                self.roi_waterfall = np.append(
                    self.roi_waterfall[-self.waterfall_size + 1 :, :],
                    np.array(
                        [
                            [self.roi_azimuth, self.roi_elevation, sensor]
                            if self.roi_enabled
                            else [None, None, sensor]
                        ]
                    ),
                    axis=0,
                )
                if args.phases_roi_wf:
                    self.roi_phases = np.append(
                        self.roi_phases[-self.waterfall_size + 1 :, :],
                        np.array([debug_phases if self.roi_enabled else [0, 0, 0]]),
                        axis=0,
                    )

                global roi_data
                global compass_data
                if self.roi_enabled and compass is not None:
                    roi_data = np.append(
                        roi_data,
                        np.array([[self.roi_azimuth, self.roi_elevation]]),
                        axis=0,
                    )
                    compass_data = np.append(
                        compass_data,
                        np.array([compass.compass]),
                        axis=0,
                    )
                elif compass is not None:
                    roi_data = np.append(
                        roi_data,
                        np.array([["NaN", "NaN"]]),
                        axis=0,
                    )
                    compass_data = np.append(
                        compass_data,
                        np.array([compass.compass]),
                        axis=0,
                    )

            # self.status_label_ref.config(
            #     text=f"Packet {packet.packet_index} - Stream {packet.stream_id}, index {packet.sample_index}"
            #          f" | Queue count: {packets_queue.qsize()}"
            # )

        self.animation_started = False
        stream_process.join()
        stream_process.terminate()

    @typing.no_type_check  # no typing for matplotlib
    def create_anim(
        self,
        bin_count: int,
        data_bin_count: int,
        center_freq: float,
        iq_rate: float,
        vmin: float,
        vmax: float,
    ) -> None:
        global args
        pi_chr = chr(0x03C0)
        """
        Creates matplotlib animation on the GUI
        """
        assert self.recreate_canvas_action
        self.recreate_canvas_action()

        data_bin_count_ratio = bin_count / data_bin_count

        class HalfLocator(matplotlib.ticker.Locator):  # type: ignore
            """
            Tick locator for matplotlib plot
            Set a tick on each integer multiple of a base within the view interval.
            """

            def __init__(self, max: float = 1.0) -> None:
                self._max = max

            def set_params(self, max: float) -> None:
                """Set parameters within this locator."""
                if max is not None:
                    self._max = max

            def __call__(self) -> list[float]:
                """Return the locations of the ticks."""
                vmin, vmax = self.axis.get_view_interval()
                return self.tick_values(vmin, vmax)

            def tick_values(self, vmin: float, vmax: float) -> list[float]:
                if vmax < vmin:
                    vmin, vmax = vmax, vmin

                step = self._max / 4
                locs: list[float] = []
                while len(locs) < 4:
                    locs = [
                        loc
                        for loc in np.arange(0, self._max, step)
                        if vmin <= loc <= vmax
                    ]
                    step /= 2
                if self._max <= vmax:
                    locs.append(self._max)
                return self.raise_if_exceeds(locs)

            def view_limits(self, dmin: float, dmax: float) -> tuple[float, float]:
                """
                Set the view limits
                """
                return matplotlib.transforms.nonsingular(
                    dmin, dmax, expander=1e-12, tiny=1e-13
                )

        def update_imag(frame_number: int) -> list[matplotlib.artist.Artist]:
            """
            Called on each frame of the graph animation
            """
            update_list: list[matplotlib.artist.Artist] = [self.magnitude_image]
            self.magnitude_image.set_data(self.waterfall)
            if args.roi_wf:
                self.roi_waterfall_azimuth_image.set_xdata(self.roi_waterfall[:, 0])
                self.roi_waterfall_elevation_image.set_xdata(self.roi_waterfall[:, 1])
                self.roi_waterfall_compass_image.set_xdata(self.roi_waterfall[:, 2])
                update_list.extend(
                    [
                        self.roi_waterfall_azimuth_image,
                        self.roi_waterfall_elevation_image,
                        self.roi_waterfall_compass_image,
                    ]
                )
                if args.phases_roi_wf:
                    self.roi_waterfall_phase1_image.set_xdata(self.roi_phases[:, 0])
                    self.roi_waterfall_phase2_image.set_xdata(self.roi_phases[:, 1])
                    self.roi_waterfall_phase3_image.set_xdata(self.roi_phases[:, 2])
                    update_list.extend(
                        [
                            self.roi_waterfall_phase1_image,
                            self.roi_waterfall_phase2_image,
                            self.roi_waterfall_phase3_image,
                        ]
                    )
            else:
                self.azimuth_image.set_ydata(self.azimuth_spectrum)
                self.elevation_image.set_ydata(self.elevation_spectrum)
                update_list.extend(
                    [
                        self.azimuth_image,
                        self.elevation_image,
                    ]
                )
                if self.roi_enabled:
                    self.azimuth_roi_image.set_xdata(self.roi_bin)
                    self.azimuth_roi_image.set_ydata(self.roi_azimuth)
                    self.elevation_roi_image.set_xdata(self.roi_bin)
                    self.elevation_roi_image.set_ydata(self.roi_elevation)
                    update_list.extend(
                        [
                            self.azimuth_roi_image,
                            self.elevation_roi_image,
                        ]
                    )

            return update_list

        def bin_freq_formatter(x: float, pos: Any = None) -> str:
            return f"{((x - data_bin_count / 2) * (iq_rate / data_bin_count) + center_freq) / 1e6:.3f}M"

        def sample_id_formatter(x: float, pos: Any = None) -> str:
            return f"{x - self.waterfall_size:.0f}"

        def magnitude_format_coord(x: float, y: float) -> str:
            return f"Frequency: {bin_freq_formatter(x)} (bin {int(x * data_bin_count_ratio)}), Packet: {sample_id_formatter(y)}"

        def azimuth_format_coord(x: float, y: float) -> str:
            if 0 < x < len(self.azimuth_spectrum):
                val = self.azimuth_spectrum[int(x)]
            else:
                val = 0
            return (
                f"Frequency: {bin_freq_formatter(x)} (bin {int(x * data_bin_count_ratio)}), "
                f"Angle: {val:.3f} rad ({val / np.pi * 180:.2f} deg)"
            )

        def elevation_format_coord(x: float, y: float) -> str:
            if 0 < x < len(self.elevation_spectrum):
                val = self.elevation_spectrum[int(x)]
            else:
                val = 0
            return f"Frequency: {bin_freq_formatter(x)} (bin {int(x)}), Angle: {val:.3f} rad ({val / np.pi * 180:.2f} deg)"

        def roi_format_coord(x: float, y: float) -> str:
            return (
                f"Packet: {sample_id_formatter(y)}, "
                f"Angle: {x:.3f} rad ({x / np.pi * 180:.2f} deg)"
            )

        self.waterfall = np.zeros([self.waterfall_size, data_bin_count])
        self.azimuth_spectrum = np.zeros([data_bin_count])
        self.elevation_spectrum = np.zeros([data_bin_count])
        self.roi_waterfall = np.empty([self.waterfall_size, 3])
        self.roi_waterfall.fill(None)

        self.roi_phases = np.empty([self.waterfall_size, 3])
        self.roi_phases.fill(None)

        assert self.fig_ref
        self.fig_ref.clf()
        # grid_spec = GridSpec(nrows=2, ncols=2, figure=self.fig_ref)
        grid_spec = self.fig_ref.add_gridspec(
            nrows=2, ncols=2, width_ratios=(3, 2), height_ratios=(1, 1)
        )
        self.magnitude_plot = self.fig_ref.add_subplot(grid_spec[:, 0])
        self.magnitude_image = self.magnitude_plot.imshow(
            self.waterfall,
            cmap=matplotlib.cm.get_cmap("gnuplot"),
            animated=True,
            vmax=vmax,
            vmin=vmin,
        )

        self.magnitude_plot.xaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(bin_freq_formatter)
        )
        self.magnitude_plot.xaxis.set_major_locator(HalfLocator(max=data_bin_count))
        self.magnitude_plot.tick_params(axis="x", labelrotation=45)
        self.magnitude_plot.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(sample_id_formatter)
        )
        self.magnitude_plot.format_coord = magnitude_format_coord
        self.fig_ref.colorbar(self.magnitude_image)

        self.magnitude_plot.set_label("Magnitude")
        self.magnitude_plot.set_ylabel("Packets")
        self.magnitude_plot.set_aspect("auto")
        if args.roi_wf:
            self.roi_waterfall_plot = self.fig_ref.add_subplot(grid_spec[:, 1])

            self.roi_waterfall_azimuth_image = self.roi_waterfall_plot.plot(
                self.roi_waterfall[:, 0],
                np.arange(0, self.waterfall_size),
                lw=1,
                color="green",
                animated=True,
                label="Az",
                zorder=100,
            )[0]
            self.roi_waterfall_elevation_image = self.roi_waterfall_plot.plot(
                self.roi_waterfall[:, 1],
                np.arange(0, self.waterfall_size),
                lw=1,
                color="blue",
                animated=True,
                label="El",
                zorder=50,
            )[0]
            if args.phases_roi_wf:
                self.roi_waterfall_phase1_image = self.roi_waterfall_plot.plot(
                    self.roi_phases[:, 0],
                    np.arange(0, self.waterfall_size),
                    lw=2,
                    color="lightgreen",
                    animated=True,
                    label="ch0-ch1",
                    zorder=10,
                )[0]
                self.roi_waterfall_phase2_image = self.roi_waterfall_plot.plot(
                    self.roi_phases[:, 1],
                    np.arange(0, self.waterfall_size),
                    lw=2,
                    color="lightblue",
                    animated=True,
                    label="ch0-ch2",
                    zorder=5,
                )[0]
                self.roi_waterfall_phase3_image = self.roi_waterfall_plot.plot(
                    self.roi_phases[:, 2],
                    np.arange(0, self.waterfall_size),
                    lw=2,
                    color="lightpink",
                    animated=True,
                    label="ch0-ch3",
                    zorder=0,
                )[0]

            self.roi_waterfall_compass_image = self.roi_waterfall_plot.plot(
                self.roi_waterfall[:, 2],
                np.arange(0, self.waterfall_size),
                lw=1,
                color="red",
                animated=True,
                label="Sensor",
            )[0]
            self.roi_waterfall_plot.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(sample_id_formatter)
            )
            self.roi_waterfall_plot.set_ylabel("Packets")
            self.roi_waterfall_plot.set_aspect("auto")

            self.roi_waterfall_plot.xaxis.set_major_formatter(
                matplotlib.ticker.StrMethodFormatter("{x:.2f}")
            )
            self.roi_waterfall_plot.grid(axis="both")
            self.roi_waterfall_plot.set_xlim(-np.pi, np.pi)
            self.roi_waterfall_plot.set_xticks(
                [-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi]
            )
            self.roi_waterfall_plot.set_xticklabels(
                [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
            )
            self.roi_waterfall_plot.format_coord = roi_format_coord
            self.roi_waterfall_plot.set_label("ROI Waterfall")
            self.roi_waterfall_plot.set_aspect("auto")
            self.roi_waterfall_plot.invert_yaxis()
            self.roi_waterfall_plot.set_ylim(self.waterfall_size, 0)
            self.roi_waterfall_plot.yaxis.set_label_position("right")
            self.roi_waterfall_plot.yaxis.tick_right()
            self.roi_waterfall_plot.legend()
        else:
            self.azimuth_plot = self.fig_ref.add_subplot(grid_spec[0, 1])
            self.elevation_plot = self.fig_ref.add_subplot(grid_spec[1, 1])

            self.azimuth_image = self.azimuth_plot.plot(
                self.azimuth_spectrum, lw=1, color="green", animated=True
            )[0]
            self.azimuth_roi_image = self.azimuth_plot.plot(0, 0, "or", animated=True)[
                0
            ]
            self.elevation_image = self.elevation_plot.plot(
                self.elevation_spectrum, lw=1, color="blue", animated=True
            )[0]
            self.elevation_roi_image = self.elevation_plot.plot(
                0, 0, "or", animated=True
            )[0]

            self.azimuth_plot.xaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(bin_freq_formatter)
            )
            self.azimuth_plot.xaxis.set_major_locator(HalfLocator(max=data_bin_count))
            self.azimuth_plot.tick_params(axis="x", labelrotation=45)
            self.azimuth_plot.yaxis.set_major_formatter(
                matplotlib.ticker.StrMethodFormatter("{x:.2f}")
            )
            self.azimuth_plot.grid(axis="both")
            self.azimuth_plot.format_coord = azimuth_format_coord
            self.azimuth_plot.set_ylim(-np.pi, np.pi)
            self.azimuth_plot.set_yticks([-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi])
            self.azimuth_plot.set_yticklabels(
                [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
            )
            self.azimuth_plot.set_ylabel("Azimuth")
            self.azimuth_plot.set_label("Azimuth")
            self.azimuth_plot.set_aspect("auto")

            self.elevation_plot.xaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(bin_freq_formatter)
            )
            self.elevation_plot.xaxis.set_major_locator(HalfLocator(max=data_bin_count))
            self.elevation_plot.tick_params(axis="x", labelrotation=45)
            self.elevation_plot.yaxis.set_major_formatter(
                matplotlib.ticker.StrMethodFormatter("{x:.2f}")
            )
            self.elevation_plot.grid(axis="both")
            self.elevation_plot.format_coord = elevation_format_coord
            self.elevation_plot.set_ylim(-np.pi, np.pi)
            self.elevation_plot.set_yticks([-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi])
            self.elevation_plot.set_yticklabels(
                [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
            )
            self.elevation_plot.set_ylabel("Elevation")
            self.elevation_plot.set_label("Elevation")
            self.elevation_plot.set_aspect("auto")

        self.animation = FuncAnimation(
            self.fig_ref, update_imag, interval=int(1000 / args.fps), blit=True
        )
        grid_spec.tight_layout(figure=self.fig_ref)
        grid_spec.update()
        self.fig_ref.canvas.draw()


class ClientWindow(tkinter.Frame):
    def __init__(self) -> None:
        global args
        super().__init__()
        self.fig: Optional[pyplot.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.canvas_toolbar: Optional[NavigationToolbar2Tk] = None

        self.pack(fill=tkinter.BOTH, expand=1)

        self.host_command = tkinter.StringVar(value="localhost:12936")
        """
        Variable for the current value of the command host textbox
        """

        self.host_stream = tkinter.StringVar(value="localhost:12937")
        """
        Variable for the current value of the stream host textbox
        """

        # Load host settings into the address boxes
        if os.path.exists("hosts.txt"):
            with open("hosts.txt") as f:
                self.host_command.set(f.readline().strip())
                self.host_stream.set(f.readline().strip())

        self.command_string = tkinter.StringVar(value="")
        """
        Variable for the current value of the command box
        """

        status_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        status_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        status_command_label_label = tkinter.Label(
            status_frame,
            text="Command:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_command_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_command_label = tkinter.Label(
            status_frame, text="Not connected", font=tkinter.font.Font(size=10)
        )
        self.status_command_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_stream_label_label = tkinter.Label(
            status_frame,
            text="Stream:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_stream_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_stream_label = tkinter.Label(
            status_frame, text="Not connected", font=tkinter.font.Font(size=10)
        )
        self.status_stream_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        connect_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        connect_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        self.save_octave_button = tkinter.Button(
            connect_frame, text="Save Octave", command=self.save_octave_commands
        )
        self.save_octave_button.pack(side=tkinter.LEFT)
        host_command_label = tkinter.Label(connect_frame, text="Command host:")
        host_command_label.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=5, pady=10, expand=True
        )

        self.host_command_entry = tkinter.Entry(
            connect_frame, textvariable=self.host_command
        )
        self.host_command_entry.pack(side=tkinter.LEFT, padx=5, expand=True)

        host_stream_label = tkinter.Label(connect_frame, text="Stream host:")
        host_stream_label.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=5, pady=10, expand=True
        )

        self.host_stream_entry = tkinter.Entry(
            connect_frame, textvariable=self.host_stream
        )
        self.host_stream_entry.pack(side=tkinter.LEFT, padx=5, expand=True)

        self.disconnect_button = tkinter.Button(
            connect_frame, text="Disconnect", command=self.disconnect_commands
        )
        self.disconnect_button.pack(side=tkinter.RIGHT, padx=5, pady=5)
        self.disconnect_button.configure(state="disabled")

        self.connect_button = tkinter.Button(
            connect_frame, text="Connect", command=self.connect_commands
        )
        self.connect_button.pack(side=tkinter.RIGHT)
        self.plot_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        if args.disp:
            self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        self.command_suggestions = set()

        # Load command suggestions from file
        if os.path.exists("commands.txt"):
            with open("commands.txt") as f:
                for line in f:
                    self.command_suggestions.add(line.strip())

        def save_command_to_suggestions(command: str) -> None:
            """
            Save command to suggestions. Called when sending a command to the server.
            """
            self.command_suggestions.add(command)
            # Also save fragments of commands
            if ":" in command:  # Save command group fragment.
                self.command_suggestions.add(command.split(":")[0] + ":")
            if "?" in command:  # Save command without arguments.
                self.command_suggestions.add(command.split("?")[0] + "?")
            if "!" in command:  # Save command without arguments.
                self.command_suggestions.add(command.split("!")[0] + "!")
            command_history_sorted = list(self.command_suggestions)
            command_history_sorted.sort()
            with open("commands.txt", "w") as f1:
                f1.writelines(h + "\n" for h in command_history_sorted)

        bottom_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        bottom_frame.pack(fill=tkinter.BOTH, expand=not args.disp, side=tkinter.TOP)
        command_frame = tkinter.Frame(
            bottom_frame, relief=tkinter.RAISED, borderwidth=1
        )
        command_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.LEFT)
        if args.disp:
            self.console_textarea = tkinter.Text(command_frame, height=5, width=52)
        else:
            self.console_textarea = tkinter.Text(command_frame, width=40)
        self.console_textarea.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        self.console_textarea.configure(state="disabled")

        # Configure a tag for the console area to indicate sent commands with blue
        # (received response will be default black)
        self.console_textarea.tag_configure("i", foreground="blue")

        self.command_thread: Optional[CommandsConnectionThread] = None
        self.stream_thread: Optional[StreamDisplayThread] = None

        def send_cmd(*args: Any) -> None:
            """
            Send the command from the command entry box to the client. Called on pressing the Return key.
            """
            assert self.command_thread
            assert self.command_thread.client_socket
            cmd = self.command_string.get().replace("\n", "").replace("\r", "")
            self.command_string.set("")
            for cmd_line in cmd.split(";"):  # One command per line
                if not cmd_line:
                    continue
                cmd_line = cmd_line.strip()
                cmd_line += ";"
                save_command_to_suggestions(cmd_line)
                self.command_thread.client_socket.send(cmd_line.encode())
                self.console_textarea.configure(
                    state="normal"
                )  # Textarea has to be unlocked to enable modification
                self.console_textarea.insert(tkinter.END, "\n")
                self.console_textarea.insert(tkinter.END, cmd_line)
                self.console_textarea.tag_add(
                    "i", "end -1 lines", "end -1 chars"
                )  # Tag, so that it will be blue
                self.console_textarea.see(tkinter.END)  # Scroll to the bottom
                self.console_textarea.configure(state="disabled")  # Block user editing
                sleep(0.1)

        def suggestions_filter(*args: Any) -> None:
            """
            Filter the suggestions box. Called when a letter is typed to the command input box.
            """
            command_suggestions_lb.delete(0, tkinter.END)  # Clear suggestions box
            command_history_sorted = list(self.command_suggestions)
            command_history_sorted.sort()
            typed_command_string = (
                self.command_string.get()
            )  # Typed in command (fragment)
            if ":" not in typed_command_string:
                # If no ":" yet, display only command beginning fragments
                command_history_sorted = list(
                    filter(
                        lambda command: ":" not in command or command.endswith(":"),
                        command_history_sorted,
                    )
                )
            if not ("?" in typed_command_string or "!" in typed_command_string):
                # Do not display commands with arguments, if the whole command has not been typed yet.
                command_history_sorted = list(
                    filter(
                        lambda command: ("!" not in command and "?" not in command)
                        or command.endswith("!")
                        or command.endswith("?"),
                        command_history_sorted,
                    )
                )
            for history_item in command_history_sorted:
                if history_item.upper().startswith(typed_command_string.upper()):
                    command_suggestions_lb.insert(tkinter.END, history_item)

        def autocomplete(*args: Any) -> str:
            """
            Grab the first from the suggestions. Called on the Tab key.
            """
            self.command_string.set(command_suggestions_lb.get(0))
            self.command_entry.focus()
            self.command_entry.icursor(tkinter.END)
            return "break"

        def to_suggestions_list(*args: Any) -> str:
            """
            Move from the command input box to the suggestions list. Called on the Down key.
            """
            command_suggestions_lb.focus()
            self.command_string.set(command_suggestions_lb.get(0))
            return "break"

        def select_suggestion_cmd(*args: Any) -> None:
            """
            Select a command from the list and use it in the command input box.
            """
            if command_suggestions_lb.size() > 0:
                curselection = command_suggestions_lb.curselection()  # type: ignore
                # strange values when nothing selected
                if curselection not in [(), "", None]:
                    self.command_string.set(command_suggestions_lb.get(curselection[0]))

        def to_command_box(*args: Any) -> str:
            """
            Return from the command suggestion list to the command input box. Called on the Enter or Tab key.
            """
            self.command_entry.focus()
            self.command_entry.icursor(tkinter.END)
            suggestions_filter()
            return "break"

        self.command_entry = tkinter.Entry(
            command_frame, textvariable=self.command_string
        )
        self.command_entry.pack(side=tkinter.TOP, fill=tkinter.X, padx=5, expand=True)
        self.command_entry.bind("<Return>", send_cmd)
        self.command_entry.bind("<KeyRelease>", suggestions_filter)
        self.command_entry.bind("<Tab>", autocomplete)
        self.command_entry.bind("<Down>", to_suggestions_list)
        self.command_entry.configure(state="disabled")

        command_suggestions_lb = tkinter.Listbox(command_frame, height=4)

        command_suggestions_lb.bind("<<ListboxSelect>>", select_suggestion_cmd)
        command_suggestions_lb.bind("<Tab>", to_command_box)
        command_suggestions_lb.bind("<Return>", to_command_box)
        command_suggestions_lb.bind("<Double-Button>", to_command_box)

        command_suggestions_lb.pack(
            side=tkinter.TOP, fill=tkinter.X, padx=5, expand=False
        )
        suggestions_filter()

        self.stream_packets_lb = tkinter.Listbox(bottom_frame, height=4)
        self.stream_packets_lb.pack(
            side=tkinter.RIGHT, fill=tkinter.BOTH, padx=6, expand=True
        )
        if args.sensor_dev:
            global compass
            compass = CompassSensor()
            compass.start()

    def create_canvas(self) -> None:
        """
        Creates matplotlib canvas for graph plots. Called when connecting to the client.
        """
        if self.fig is not None:
            self.fig.gca().cla()  # type: ignore
        if self.canvas is not None:  # Remove old widget if there is one
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
        if self.canvas_toolbar is not None:
            self.canvas_toolbar.destroy()
            self.canvas_toolbar = None
        self.fig = pyplot.Figure(tight_layout=True)  # type: ignore
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(
            side=tkinter.TOP, fill=tkinter.BOTH, expand=True
        )

        self.canvas_toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.canvas_toolbar.update()

        def on_canvas_key_press(event: KeyEvent) -> None:
            key_press_handler(event, self.canvas, self.canvas_toolbar)

        self.canvas.mpl_connect("key_press_event", on_canvas_key_press)
        self.canvas_toolbar.pack(side=tkinter.TOP, fill=tkinter.X, expand=False)
        if self.stream_thread is not None:
            self.stream_thread.fig_ref = self.fig
            self.command_entry.focus()

    def connect_action(self) -> None:
        """
        Events triggered by successful connection
        """
        self.connect_button.configure(state="disabled")
        self.host_command_entry.configure(state="disabled")
        self.host_stream_entry.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.command_entry.configure(state="normal")
        self.command_entry.focus()

    def disconnect_action(self) -> None:
        """
        Events triggered by client disconnect
        """
        try:
            self.disconnect_button.configure(state="disabled")
            self.command_entry.configure(state="disabled")
            self.host_command_entry.configure(state="normal")
            self.host_stream_entry.configure(state="normal")
            self.connect_button.configure(state="normal")
            self.command_string.set("")
            self.disconnect_commands()  # to disconnect the other thread
        except RuntimeError:
            pass  # it might happen when closing the window

    def connect_commands(self) -> None:
        """
        Action of the "Connect" button
        """
        self.command_thread = CommandsConnectionThread()
        self.command_thread.console_textarea_ref = self.console_textarea
        self.command_thread.connect_action = self.connect_action
        self.command_thread.disconnect_action = self.disconnect_action
        self.command_thread.host_port = self.host_command.get()
        self.command_thread.status_label_ref = self.status_command_label
        self.command_thread.start()
        self.stream_thread = StreamDisplayThread()
        self.stream_thread.recreate_canvas_action = self.create_canvas
        self.stream_thread.host_port = self.host_stream.get()
        self.stream_thread.status_label_ref = self.status_stream_label
        self.stream_thread.packets_lb_ref = self.stream_packets_lb
        self.stream_thread.start()
        with open("hosts.txt", "w") as f1:
            f1.write(self.host_command.get() + "\n")
            f1.write(self.host_stream.get() + "\n")

    def save_octave_commands(self) -> None:
        """
        Action of the "Connect" button
        """
        with open(f"octave{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w") as f1:
            global roi_data
            global compass_data
            f1.writelines(
                "\n".join(
                    [
                        "# Created by CSTestClient, " + str(datetime.now()),
                        "# name: roi",
                        "# type: matrix",
                        "# rows: " + str(roi_data.shape[0]),
                        "# columns: 2",
                    ]
                )
            )
            f1.write("\n")
            f1.writelines("\n".join([" ".join(row.astype(str)) for row in roi_data]))
            f1.write("\n\n")

            f1.writelines(
                "\n".join(
                    [
                        "# name: compass",
                        "# type: matrix",
                        "# rows: " + str(compass_data.shape[0]),
                        "# columns: 3",
                    ]
                )
            )
            f1.write("\n\n")
            f1.writelines(
                "\n".join([" ".join(row.astype(str)) for row in compass_data])
            )
            f1.write("\n\n")
            roi_data = np.empty([0, 2])
            compass_data = np.empty([0, 3])

    def disconnect_commands(self) -> None:
        """
        Action of the "Disconnect" button
        """
        if self.command_thread is not None:
            self.command_thread.disconnect = True
        if self.stream_thread is not None:
            self.stream_thread.disconnect = True
            if self.stream_thread.disconnect_value is not None:
                self.stream_thread.disconnect_value.value = True


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = ClientWindow()
    root.geometry("1024x768")
    root.wm_title("CS Test Client")
    root.mainloop()
    ex.disconnect_commands()
