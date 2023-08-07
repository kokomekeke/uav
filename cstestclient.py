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
import struct
import threading
import time
import tkinter
import typing
from datetime import datetime
from time import sleep
from tkinter import messagebox
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

import pysagax
from pysagax import (
    AngleSpectrumGraph,
    BaseConnection,
    CompassSensor,
    CoreServicePacket,
    GraphImage,
    GraphParameters,
    StreamConnectionProcess,
    WaterfallAngleGraph,
    WaterfallMagnitudeGraph,
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
parser.add_argument(
    "--aaronia",
    dest="aaronia",
    default=False,
    action="store_true",
    help="compass sensor is aaronia",
)
args = parser.parse_args()

roi_data = np.empty([0, 2])
compass_data = np.empty([0, 1])
phases_data = np.empty([0, 3])

compass: Optional[CompassSensor] = None
octave_recording = False


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


"""
This thread is responsible for handling the multiprocessing stream process and for displaying the stream contents
on the matplotlib plots
"""


class TestStreamDisplayThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__()
        global args
        self.params = GraphParameters()
        self.params.waterfall_size = args.wf
        """
        Amount of spectrum lines to be displayed on the waterfall diagram.
        """

        self.fig_ref: Optional[pyplot.Figure] = None
        """
        Reference to the matplotlib figure.
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

        self.magnitude_graph: Optional[WaterfallMagnitudeGraph] = None
        """
        Matplotlib image object for the magnitude plot
        """

        self.azimuth_graph: Optional[AngleSpectrumGraph] = None
        """
        Matplotlib image object for the azimuth plot
        """

        self.elevation_graph: Optional[AngleSpectrumGraph] = None
        """
        Matplotlib image object for the elevation plot
        """

        self.roi_waterfall_compass: Optional[WaterfallAngleGraph] = None
        """
        Matplotlib image object for the ROI waterfall compass sensor
        """

        self.roi_waterfall_azimuth_graph: Optional[WaterfallAngleGraph] = None
        """
        Matplotlib image object for the ROI waterfall azimuth
        """

        self.roi_waterfall_elevation_graph: Optional[WaterfallAngleGraph] = None
        """
        Matplotlib image object for the ROI waterfall elevation
        """

        self.roi_waterfall_phase_graph: list[Optional[WaterfallAngleGraph]] = [
            None,
            None,
            None,
        ]
        """
        Matplotlib image object for the ROI waterfall Phases
        """

        self.animation: Optional[matplotlib.animation.FuncAnimation] = None
        """
        Matplotlib FuncAnimation object for animating the graphs
        """

        self.animation_started: bool = False
        """
        Indicates whether the animation and plot objects have been created
        """

        self.graph_list: list[GraphImage] = []

        self.status_label_ref: Optional[tkinter.Label] = None
        """
        Reference of the status label on the main window
        """

        self.packets_lb_ref: Optional[tkinter.Listbox] = None
        """
        Reference of the packets listbox on the main window
        """

        self.recreate_canvas_action: Optional[Callable[[], None]] = None
        """
        Action that recreates plot canvas
        """

        self.roi_packet: Optional[CoreServicePacket] = None
        """
        Latest ROI packet
        """

        self.roi_bin: int = 0
        """
        FFT bin position of ROI result
        """

        self.debug_phases: list[float] = [0.0, 0.0, 0.0]
        """
        Channel phase differences on the current ROI bin
        """

        self.disconnect: bool = False
        """
        When the disconnect flag is set, the thread loop will quit on the next iteration.
        """

        self.host_port = ""
        """
        Host and port in <address>:<tcp port> format.
        """

        self.notification_message = ""
        """
        Last notification message from the stream port
        """

        manager = multiprocessing.get_context("spawn").Manager()
        self.disconnect_value = manager.Value("i", 0)
        """
        Setting the '1' value of the disconnect_value multiprocessing variable will end the multiprocessing task on the
        next iteration.
        """

        self.packet_handlers: dict[int, Callable[[CoreServicePacket], None]] = {
            1: self.handle_spectrum_packet,
            2: self.handle_eof_packet,
            3: self.handle_roi_result_packet,
            4: self.handle_roi_lack_of_signal_packet,
            6: self.handle_debug_packet,
        }
        self.debug_handlers: dict[str, Callable[[CoreServicePacket], None]] = {
            "error": self.handle_debug_error_message,
            "warning": self.handle_debug_warning_message,
            "notification": self.handle_debug_notification_message,
            "exportPhaseDiffs": self.handle_debug_phases_packet,
        }

    def status_watcher_thread(
        self, status_queue: queue.Queue[str], packet_string_queue: queue.Queue[str]
    ) -> None:
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
                        disp_message = (
                            f"{self.notification_message}\n{message}"
                            if self.notification_message
                            else message
                        )
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

    def log_octave_data(self) -> None:
        if not octave_recording:
            return
        global args
        global roi_data
        global compass_data
        global phases_data

        phases_data = np.append(
            phases_data,
            np.array(
                [
                    self.debug_phases
                    if self.roi_packet and args.phases_roi_wf
                    else [0, 0, 0]
                ]
            ),
            axis=0,
        )
        roi_data = np.append(
            roi_data,
            np.array(
                [
                    [self.roi_packet.roi_azimuth, self.roi_packet.roi_elevation]
                    if self.roi_packet is not None
                    else ["NaN", "NaN"]  # type: ignore
                ]
            ),
            axis=0,
        )
        compass_data = np.append(
            compass_data,
            np.array([[compass.angle] if compass is not None else ["NaN"]]),  # type: ignore
            axis=0,
        )

    def read_from_compass_sensor(self) -> None:
        global compass
        if compass is not None and self.roi_waterfall_compass is not None:
            self.roi_waterfall_compass.add_point(compass.angle)

    def handle_spectrum_packet(self, packet: CoreServicePacket) -> None:
        if packet.bin_count == 0:
            return
        if not args.disp:
            return
        if (
            not self.animation_started  # start matplotlib animation if it has not started yet
            or packet.bin_count
            != self.params.bin_count  # or restart if the dimensions change
            or packet.center_frequency
            != self.params.center_frequency  # or restart if the axes change
            or packet.iq_rate != self.params.iq_rate
        ):
            # Animation can be created, because at this point we know bin count and other properties
            # Also restart when bin count or any other parameter has changed
            self.params.bin_count = packet.bin_count
            self.params.iq_rate = packet.iq_rate
            self.params.center_frequency = packet.center_frequency
            self.create_anim()
            self.animation_started = True
        assert self.magnitude_graph is not None
        self.magnitude_graph.add_data(packet.magnitude_spectrum)
        self.read_from_compass_sensor()
        self.log_octave_data()
        if args.roi_wf:
            assert self.roi_waterfall_azimuth_graph is not None
            assert self.roi_waterfall_elevation_graph is not None
            self.roi_waterfall_azimuth_graph.add_point(
                self.roi_packet.roi_azimuth if self.roi_packet else None
            )
            self.roi_waterfall_elevation_graph.add_point(
                self.roi_packet.roi_elevation if self.roi_packet else None
            )

            if args.phases_roi_wf:
                for graph, i in zip(self.roi_waterfall_phase_graph, range(3)):
                    if graph is not None:
                        graph.add_point(self.debug_phases[i] if self.roi_packet else 0)

        else:
            assert self.azimuth_graph is not None
            assert self.elevation_graph is not None
            self.azimuth_graph.set_data(packet.azimuth_spectrum)
            self.elevation_graph.set_data(packet.elevation_spectrum)
            self.azimuth_graph.marker_bin = self.roi_bin

    def handle_eof_packet(self, packet: CoreServicePacket) -> None:
        pass

    def handle_roi_result_packet(self, packet: CoreServicePacket) -> None:
        if self.params.iq_rate == 0:
            self.roi_bin = 0
        else:
            self.roi_bin = int(
                (packet.center_frequency - self.params.center_frequency)
                * (self.params.bin_count / self.params.iq_rate)
                + self.params.bin_count / 2
            )
            self.roi_packet = packet

    def handle_roi_lack_of_signal_packet(self, packet: CoreServicePacket) -> None:
        self.roi_packet = None

    def handle_debug_packet(self, packet: CoreServicePacket) -> None:
        self.debug_handlers[packet.title](packet)

    def handle_debug_notification_message(self, packet: CoreServicePacket) -> None:
        self.notification_message = packet.contents.decode()

    def handle_debug_warning_message(self, packet: CoreServicePacket) -> None:
        messagebox.showwarning(packet.title.capitalize(), packet.contents.decode())

    def handle_debug_error_message(self, packet: CoreServicePacket) -> None:
        messagebox.showerror(packet.title.capitalize(), packet.contents.decode())

    def handle_debug_phases_packet(self, packet: CoreServicePacket) -> None:
        spec_len = self.params.bin_count * 4
        ch1_spectrum: npt.NDArray[np.float32] = np.asarray(
            struct.unpack(
                f"{self.params.bin_count}f",
                packet.contents[0:spec_len],
            )
        )  # type: ignore
        ch2_spectrum: npt.NDArray[np.float32] = np.asarray(
            struct.unpack(
                f"{self.params.bin_count}f",
                packet.contents[spec_len : spec_len * 2],
            )
        )  # type: ignore
        ch3_spectrum: npt.NDArray[np.float32] = np.asarray(
            struct.unpack(
                f"{self.params.bin_count}f",
                packet.contents[spec_len * 2 : spec_len * 3],
            )
        )  # type: ignore
        if self.roi_bin < self.params.bin_count:
            self.debug_phases = [
                float(ch1_spectrum[self.roi_bin]),
                float(ch2_spectrum[self.roi_bin]),
                float(ch3_spectrum[self.roi_bin]),
            ]

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

        # The purpose of the watcher thread is to take the status messages from the multiprocessing process and display
        # them on the GUI, and to forward the disconnect signal to the process if the "Disconnect" button is clicked.
        watcher_thread = threading.Thread(
            target=self.status_watcher_thread,
            args=(status_queue, packet_string_queue),
            daemon=True,
        )
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
            self.packet_handlers[packet.packet_type](packet)

        self.animation_started = False
        stream_process.join()
        stream_process.terminate()

    def update_imag(self, frame_number: int) -> list[matplotlib.artist.Artist]:
        image_list = []
        for graph in self.graph_list:
            graph.update()
            image_list.extend(graph.collect_images())
        return image_list

    def create_anim(self) -> None:
        global args
        """
        Creates matplotlib animation on the GUI
        """
        assert self.recreate_canvas_action
        self.recreate_canvas_action()

        assert self.fig_ref
        self.fig_ref.clf()

        grid_spec = self.fig_ref.add_gridspec(  # type: ignore
            nrows=2, ncols=2, width_ratios=(3, 2), height_ratios=(1, 1)
        )
        self.magnitude_plot = self.fig_ref.add_subplot(grid_spec[:, 0])
        self.magnitude_graph = WaterfallMagnitudeGraph(
            self.magnitude_plot, self.params
        ).initialize()
        colorbar = self.fig_ref.colorbar(  # type: ignore
            self.magnitude_graph.image, format=lambda x, _: f"{x:.0f}dB"
        )
        self.magnitude_graph.make_plot()
        if args.roi_wf:
            self.roi_waterfall_plot = self.fig_ref.add_subplot(grid_spec[:, 1])
            if args.phases_roi_wf:
                for i, color in zip(range(3), ["lightgreen", "lightblue", "lightpink"]):
                    self.roi_waterfall_phase_graph[i] = WaterfallAngleGraph(
                        self.roi_waterfall_plot, self.params
                    ).initialize(color, f"ch{i+1}-ch0")
            global compass
            if compass is not None:
                self.roi_waterfall_compass = WaterfallAngleGraph(
                    self.roi_waterfall_plot, self.params
                ).initialize("red", "Compass")
            self.roi_waterfall_azimuth_graph = WaterfallAngleGraph(
                self.roi_waterfall_plot, self.params
            ).initialize("green", "Azim")
            self.roi_waterfall_elevation_graph = (
                WaterfallAngleGraph(self.roi_waterfall_plot, self.params)
                .initialize("blue", "Elev")
                .make_plot()
            )
        else:
            self.azimuth_plot = self.fig_ref.add_subplot(grid_spec[0, 1])
            self.azimuth_graph = (
                AngleSpectrumGraph(self.azimuth_plot, self.params)
                .initialize("green")
                .make_plot()
            )
            self.elevation_plot = self.fig_ref.add_subplot(grid_spec[1, 1])
            self.elevation_graph = (
                AngleSpectrumGraph(self.elevation_plot, self.params)
                .initialize("blue")
                .make_plot()
            )

        self.graph_list = [
            graph
            for graph in [
                self.magnitude_graph,
                self.azimuth_graph,
                self.elevation_graph,
                self.roi_waterfall_azimuth_graph,
                self.roi_waterfall_elevation_graph,
                self.roi_waterfall_phase_graph[0],
                self.roi_waterfall_phase_graph[1],
                self.roi_waterfall_phase_graph[2],
                self.roi_waterfall_compass,
            ]
            if graph is not None
        ]
        self.animation = FuncAnimation(
            self.fig_ref, self.update_imag, interval=int(1000 / args.fps), blit=True
        )

        grid_spec.tight_layout(figure=self.fig_ref)
        grid_spec.update()

        self.fig_ref.canvas.draw()  # type: ignore


class ClientWindow(tkinter.Frame):
    def __init__(self) -> None:
        global args
        super().__init__()

        self.command_thread: Optional[CommandsConnectionThread] = None
        self.stream_thread: Optional[TestStreamDisplayThread] = None

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
            connect_frame, text="Rec Octave", command=self.save_octave_commands
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
        self.plot_frame = tkinter.Frame(self)
        self.create_canvas()
        if args.disp:
            self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        bottom_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        bottom_frame.pack(fill=tkinter.BOTH, expand=not args.disp, side=tkinter.TOP)
        command_frame = tkinter.Frame(
            bottom_frame, relief=tkinter.RAISED, borderwidth=1
        )
        command_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.LEFT)

        self.autocomplete_command_frame = pysagax.AutocompleteCommandBox(command_frame)
        self.autocomplete_command_frame.pack(
            fill=tkinter.X, expand=False, side=tkinter.BOTTOM
        )
        self.autocomplete_command_frame.send_command_action = self.send_command
        self.autocomplete_command_frame.initialize()

        # Load command suggestions from file
        if os.path.exists("commands.txt"):
            with open("commands.txt") as f:
                for line in f:
                    self.autocomplete_command_frame.command_suggestions.add(
                        line.strip()
                    )
        self.autocomplete_command_frame.suggestions_filter()

        self.console_textarea = tkinter.Text(command_frame, height=6, width=40)
        self.console_textarea.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        self.console_textarea.configure(state="disabled")

        # Configure a tag for the console area to indicate sent commands with blue
        # (received response will be default black)
        self.console_textarea.tag_configure("i", foreground="blue")

        self.stream_packets_lb = tkinter.Listbox(bottom_frame, height=4)
        self.stream_packets_lb.pack(
            side=tkinter.RIGHT, fill=tkinter.BOTH, padx=6, expand=True
        )
        if args.sensor_dev or args.aaronia:
            global compass
            compass = CompassSensor(
                pysagax.AaroniaParser() if args.aaronia else pysagax.SimpleParser(),
            )
            try:
                compass.load_calibration()
            except FileNotFoundError:
                messagebox.showerror(
                    "Startup error",
                    "Calibration file calibration.npz not found. Make sure sgx-pc is your workdir.",
                )
            try:
                compass.set_serial_device(
                    pysagax.open_aaronia_serial_dev()
                    if args.aaronia
                    else pysagax.open_arduino_serial_dev(args.sensor_dev)
                )
            except serial.SerialException:
                messagebox.showerror(
                    "Startup error",
                    "Compass sensor not connected. Make sure it is turned on.",
                )

            compass.start()

    def save_command_to_suggestions(self, command: str) -> None:
        """
        Save command to suggestions. Called when sending a command to the server.
        """
        self.autocomplete_command_frame.add_to_suggestions(command)
        with open("commands.txt", "w") as f1:
            f1.writelines(
                h + "\n" for h in self.autocomplete_command_frame.get_sorted_commands()
            )

    def send_command(self, *args: Any) -> None:
        """
        Send the command from the command entry box to the client. Called on pressing the Return key in the autocomplete box.
        """
        assert self.command_thread
        assert self.command_thread.client_socket
        cmd = (
            self.autocomplete_command_frame.command_string.get()
            .replace("\n", "")
            .replace("\r", "")
        )
        self.autocomplete_command_frame.command_string.set("")
        for cmd_line in cmd.split(";"):  # One command per line
            if not cmd_line:
                continue
            cmd_line = cmd_line.strip()
            cmd_line += ";"
            self.save_command_to_suggestions(cmd_line)
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
            self.autocomplete_command_frame.focus_textbox()

    def connect_action(self) -> None:
        """
        Events triggered by successful connection
        """
        self.connect_button.configure(state="disabled")
        self.host_command_entry.configure(state="disabled")
        self.host_stream_entry.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.autocomplete_command_frame.enable()
        self.autocomplete_command_frame.focus_textbox()

    def disconnect_action(self) -> None:
        """
        Events triggered by client disconnect
        """
        try:
            self.disconnect_button.configure(state="disabled")
            self.autocomplete_command_frame.disable()
            self.host_command_entry.configure(state="normal")
            self.host_stream_entry.configure(state="normal")
            self.connect_button.configure(state="normal")
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
        self.stream_thread = TestStreamDisplayThread()
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
        Action of the "Rec Octave" button
        """
        global compass_data
        global phases_data
        global roi_data
        global octave_recording

        if octave_recording:
            pysagax.save_octave(
                filename=f"octave{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                variables={
                    "roi": roi_data,
                    "compass": compass_data,
                    "phases": phases_data,
                },
            )

            phases_data = np.empty([0, 3])
            roi_data = np.empty([0, 2])
            compass_data = np.empty([0, 1])
            octave_recording = False
            self.save_octave_button.config(relief="raised")
        else:
            octave_recording = True
            self.save_octave_button.config(relief="sunken")

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
