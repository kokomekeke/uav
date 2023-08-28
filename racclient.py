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
from tkinter import messagebox, ttk
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
    CompassGraph,
    MagnitudeSpectrumGraph,
)
from pysagax.sgx_dfg_map_server import DFGMapServer

parser = argparse.ArgumentParser(description="RAC client parameters")
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
    "--rec-count",
    dest="rec_count",
    metavar="N",
    type=int,
    default=0,
    help="Count of data points in the octave recording",
)
args = parser.parse_args()

roi_data = np.empty([0, 2])
compass_data = np.empty([0, 1])

compass: Optional[CompassSensor] = None
compass_heading: float = 0
df_value: Optional[float] = 2
octave_recording = False

recording_sample_callback: Optional[Callable[[], None]]

dfg_map_server = DFGMapServer()
send_cs_commands: Optional[Callable[[str], None]] = None


class CommandsConnectionThread(BaseConnection, threading.Thread):
    def __init__(self) -> None:
        super(CommandsConnectionThread, self).__init__()
        self.incoming_buffer: bytearray = bytearray()
        self.status_text: str = ""
        self.incoming_messages_queue: queue.Queue[str] = queue.Queue()

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
        self.status_text = message

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
        self.magnitude_waterfall_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the magnitude plot
        """
        self.magnitude_waterfall_graph: Optional[WaterfallMagnitudeGraph] = None
        """
        Matplotlib image object for the magnitude plot
        """

        self.magnitude_spectrum_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the magnitude plot
        """
        self.magnitude_spectrum_graph: Optional[MagnitudeSpectrumGraph] = None
        """
        Matplotlib image object for the magnitude plot
        """

        self.compass_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the compass plot
        """

        self.df_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the df compass plot
        """

        self.compass_graph: Optional[CompassGraph] = None
        """
        Matplotlib image object for the compass sensor waterfall
        """

        self.compass_df_graph: Optional[CompassGraph] = None
        """
        Matplotlib image object for the compass sensor waterfall
        """

        self.df_graph: Optional[CompassGraph] = None
        """
        Matplotlib image object for the compass sensor waterfall
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
        global recording_sample_callback
        global roi_data
        global compass_data
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
        if recording_sample_callback is not None:
            recording_sample_callback()

    def update_sensors_and_graphs(self) -> None:
        global compass
        global compass_heading
        global df_value
        global dfg_map_server
        dfg_map_server.update_timestamp()
        if compass is not None and compass.magnetometer_values is not None:
            assert self.compass_graph is not None
            assert self.compass_df_graph is not None
            angle = (
                math.atan2(
                    compass.magnetometer_values[1],
                    compass.magnetometer_values[0],
                )
                + np.pi
            )
            compass_heading = angle if angle < np.pi else angle - 2 * np.pi
            self.compass_graph.add_point(compass_heading)
            if df_value is not None:
                df_corrected = compass_heading + df_value
                df_corrected = (
                    df_corrected if df_corrected < np.pi else df_corrected - 2 * np.pi
                )
                self.compass_df_graph.add_point(df_corrected)
                dfg_map_server.update_angle(df_corrected, 1e6)
            else:
                self.compass_df_graph.add_point(None)

        if (
            compass is not None
            and compass.parser.lat is not None
            and compass.parser.lon is not None
        ):
            dfg_map_server.update_lat_lon(compass.parser.lat, compass.parser.lon)
        assert self.df_graph is not None
        self.df_graph.add_point(df_value)

    def handle_spectrum_packet(self, packet: CoreServicePacket) -> None:
        if packet.bin_count == 0:
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

        assert self.magnitude_waterfall_graph is not None
        assert self.magnitude_spectrum_graph is not None
        self.magnitude_waterfall_graph.add_data(packet.magnitude_spectrum)
        self.magnitude_spectrum_graph.add_data(packet.magnitude_spectrum)
        self.log_octave_data()

        global df_value
        df_value = self.roi_packet.roi_azimuth if self.roi_packet else None

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
        self.update_sensors_and_graphs()
        image_list = []
        for graph in self.graph_list:
            graph.update()
            image_list.extend(graph.collect_images())
        return image_list

    def click_handler(self, event: Any) -> None:
        if self.magnitude_spectrum_graph is None:
            return
        if event.inaxes == self.magnitude_spectrum_graph.plot:
            global send_cs_commands
            assert send_cs_commands is not None
            roi_span = 5000
            roi_freq = self.magnitude_spectrum_graph.coord_to_freq(event.xdata)
            print(f"{roi_freq:0f}Hz")
            send_cs_commands(
                f"ROI:CenterFrequency! {roi_freq:.0f};"
                f"ROI:Span! {roi_span:.0f};"
                f"ROI:Configure!;"
            )
            self.magnitude_spectrum_graph.roi_center = event.xdata
            self.magnitude_spectrum_graph.roi_width = int(
                roi_span * (self.params.bin_count / self.params.iq_rate)
            )

        # print(vars(event))

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
            nrows=3, ncols=2, width_ratios=(3, 2), height_ratios=(2, 1, 1)
        )
        self.magnitude_waterfall_plot = self.fig_ref.add_subplot(grid_spec[0:2, 0])
        self.magnitude_waterfall_graph = WaterfallMagnitudeGraph(
            self.magnitude_waterfall_plot, self.params
        ).initialize()
        # colorbar = self.fig_ref.colorbar(  # type: ignore
        #     self.magnitude_waterfall_graph.image, format=lambda x, _: f"{x:.0f}dB"
        # )
        self.magnitude_waterfall_graph.make_plot()

        self.magnitude_spectrum_plot = self.fig_ref.add_subplot(grid_spec[2, 0])
        self.magnitude_spectrum_graph = (
            MagnitudeSpectrumGraph(self.magnitude_spectrum_plot, self.params)
            .initialize(color="blue")
            .make_plot()
        )

        self.fig_ref.canvas.callbacks.connect("button_press_event", self.click_handler)  # type: ignore

        self.compass_plot = self.fig_ref.add_subplot(
            grid_spec[1:, 1], projection="polar"
        )
        self.df_plot = self.fig_ref.add_subplot(grid_spec[0, 1], projection="polar")
        self.df_graph = (
            CompassGraph(self.df_plot, self.params)
            .initialize("blue", "DF Angle")
            .make_plot()
        )

        self.compass_df_graph = CompassGraph(self.compass_plot, self.params).initialize(
            "blue", "DF Heading"
        )
        self.compass_graph = (
            CompassGraph(self.compass_plot, self.params)
            .initialize("red", "UAV Heading", nesw=True)
            .make_plot()
        )

        self.graph_list = [
            graph
            for graph in [
                self.magnitude_waterfall_graph,
                self.magnitude_spectrum_graph,
                self.df_graph,
                self.compass_graph,
                self.compass_df_graph,
            ]
            if graph is not None
        ]

        self.animation = FuncAnimation(
            self.fig_ref, self.update_imag, interval=int(1000 / args.fps), blit=True
        )

        grid_spec.tight_layout(figure=self.fig_ref)
        grid_spec.update()
        # self.fig_ref.canvas.draw()  # type: ignore


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

        self.host_address = tkinter.StringVar(value="10.1.1.113")

        self.freq_string = tkinter.StringVar(value="300M")
        self.bw_string = tkinter.StringVar(value="300k")
        """
        Variable for the current value of the host textbox
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

        status_compass_label_label = tkinter.Label(
            status_frame,
            text="GPS/Compass:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_compass_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_compass_label = tkinter.Label(
            status_frame, text="Not connected", font=tkinter.font.Font(size=10)
        )
        self.status_compass_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_map_server_label_label = tkinter.Label(
            status_frame,
            text="Map server:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_map_server_label_label.pack(
            side=tkinter.LEFT, padx=5, pady=10, anchor="w"
        )

        self.status_map_server_label = tkinter.Label(
            status_frame, text="Down", font=tkinter.font.Font(size=10)
        )
        self.status_map_server_label.pack(
            side=tkinter.LEFT, padx=5, pady=10, anchor="w"
        )

        connect_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        connect_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        self.save_octave_button = tkinter.Button(
            connect_frame,
            text=f"Rec {args.rec_count}" if args.rec_count else "Rec Octave",
            command=self.save_octave_commands,
        )
        self.save_octave_button.pack(side=tkinter.LEFT)

        host_label = tkinter.Label(connect_frame, text="Host:")
        host_label.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=5, pady=10, expand=True
        )

        self.host_entry = tkinter.Entry(connect_frame, textvariable=self.host_address)
        self.host_entry.pack(side=tkinter.LEFT, padx=5, expand=True)

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
        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        bottom_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        bottom_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        control_frame = tkinter.Frame(
            bottom_frame, relief=tkinter.RAISED, borderwidth=1
        )

        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)

        freq_entry_label = ttk.Label(control_frame, text="Frequency:")
        freq_entry_label.grid(column=0, row=0, sticky=tkinter.W, padx=5, pady=5)

        freq_entry = ttk.Entry(control_frame, textvariable=self.freq_string)
        freq_entry.grid(column=1, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        bw_entry_label = ttk.Label(control_frame, text="Bandwidth:")
        bw_entry_label.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=5)

        bw_entry = ttk.Entry(control_frame, textvariable=self.bw_string)
        bw_entry.grid(column=1, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        self.start_button = tkinter.Button(
            control_frame, text="Start", command=self.start_commands
        )
        self.start_button.grid(
            column=1, row=2, padx=10, pady=20, sticky=tkinter.E + tkinter.W
        )
        self.rec_button = tkinter.Button(
            control_frame, text="Rec", command=self.rec_commands
        )
        self.rec_button.grid(
            column=0, row=2, padx=10, pady=20, sticky=tkinter.E + tkinter.W
        )

        control_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.LEFT)

        stat_frame = tkinter.Frame(bottom_frame, relief=tkinter.RAISED, borderwidth=1)

        stat_frame.columnconfigure(0, weight=1)
        stat_frame.columnconfigure(1, weight=1)
        deviation_disp_label = ttk.Label(stat_frame, text="DF deviation:")
        deviation_disp_label.grid(column=0, row=3, sticky=tkinter.W, padx=5, pady=5)
        disp_font = tkinter.font.Font(family="serif", size=16)
        deviation_disp = ttk.Label(
            stat_frame,
            text="0.05 °",
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        deviation_disp.grid(
            column=1, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )
        stat_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.RIGHT)

        self.stream_packets_lb = tkinter.Listbox(bottom_frame, height=4)

        self.stream_packets_lb.pack(
            side=tkinter.BOTTOM, fill=tkinter.BOTH, padx=6, expand=True
        )

        global recording_sample_callback
        recording_sample_callback = self.recording_sample_callback

        self.status_watcher_thread = threading.Thread(
            target=self.status_watcher, daemon=True
        )
        global dfg_map_server
        dfg_map_server.start()
        self.status_watcher_thread.start()
        global send_cs_commands
        send_cs_commands = self.send_commands  # todo this is ugly

    def start_commands(self) -> None:
        connect_string = 'UHD "serial=8001680,serial=8001820" "A:A A:B"'
        freq = 145.49e6
        bw = 300000
        gain = 45
        bin_count = burst_stride = 1024
        self.send_commands(
            f"SOURCE:Path! {connect_string};"
            f"SOURCE:CenterFrequency! {freq:.0f};"
            f"SOURCE:IqRate! {bw:.0f};"
            f"SOURCE:ChannelGain! 0 {gain};"
            f"SOURCE:ChannelGain! 1 {gain};"
            f"SOURCE:ChannelGain! 2 {gain};"
            f"SOURCE:ChannelGain! 3 {gain};"
            f"AOA:BinCount! {bin_count};"
            f"SOURCE:BurstStride! {burst_stride};"
            f"SOURCE:Configure!;"
            f"AOA:Configure!;"
            f"SOURCE:Start!;"
            f"ROI:Enable! 1;"
            f"ROI:Threshold! -150;"
        )

    def rec_commands(self) -> None:
        pass  # TODO

    def send_commands(self, commands: str) -> None:
        """
        Send the commands and wait for response
        """
        assert self.command_thread
        assert self.command_thread.client_socket
        commands = commands.replace("\n", "").replace("\r", "")
        for command in commands.split(";"):  # One command per line
            if not command:
                continue
            while not self.command_thread.incoming_messages_queue.empty():
                print(
                    f"Unprocessed command message: {self.command_thread.incoming_messages_queue.get()}"
                )
            print(f"{command};")
            self.command_thread.client_socket.send(f"{command};".encode())
            try:
                response = self.command_thread.incoming_messages_queue.get(
                    block=True, timeout=30
                )
                print(response)
                response_parts = response.split(" ")
                error_code = int(response_parts[0])
                if error_code:
                    messagebox.showerror("Command error", f"{command}\n{response}")
            except queue.Empty:
                messagebox.showwarning("Timeout", f"Command {command} timed out.")

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

    def status_watcher(self) -> None:
        """
        This runs in a separate thread and keeps the status bar updated
        """
        global dfg_map_server
        global compass
        try:
            while True:
                if self.command_thread is not None:
                    self.status_command_label.config(
                        text=self.command_thread.status_text
                    )
                else:
                    self.status_command_label.config(text="Not connected")
                # Streaming manages its status label on its own
                if compass is not None:
                    ser_class = repr(compass.ser.__class__).split("'")[1]
                    self.status_compass_label.config(text=(f"Connected {ser_class}"))
                else:
                    self.status_compass_label.config(text=(f"Not connected"))

                if dfg_map_server is not None:
                    dfg_map_server.update_clients()  # send update to clients every 0.2 seconds
                    self.status_map_server_label.config(
                        text=(
                            f"Up on port {dfg_map_server.port}, "
                            f"{dfg_map_server.count_clients()} clients, "
                            f"{dfg_map_server.total_packets} packets"
                        )
                    )
                else:
                    self.status_map_server_label.config(text="Down")
                time.sleep(0.2)
        except RuntimeError:
            pass  # it might happen while closing the window

    def connect_action(self) -> None:
        """
        Events triggered by successful connection
        """
        self.connect_button.configure(state="disabled")
        self.host_entry.configure(state="disabled")
        self.disconnect_button.configure(state="normal")

    def disconnect_action(self) -> None:
        """
        Events triggered by client disconnect
        """
        try:
            self.disconnect_button.configure(state="disabled")
            self.host_entry.configure(state="normal")
            self.connect_button.configure(state="normal")
            self.disconnect_commands()  # to disconnect the other thread
        except RuntimeError:
            pass  # it might happen when closing the window

    def connect_commands(self) -> None:
        """
        Action of the "Connect" button
        """
        self.command_thread = CommandsConnectionThread()
        self.command_thread.connect_action = self.connect_action
        self.command_thread.disconnect_action = self.disconnect_action
        self.command_thread.host_port = f"{self.host_address.get()}:12936"
        self.command_thread.start()
        self.stream_thread = TestStreamDisplayThread()
        self.stream_thread.recreate_canvas_action = self.create_canvas
        self.stream_thread.host_port = f"{self.host_address.get()}:12937"
        self.stream_thread.status_label_ref = self.status_stream_label
        self.stream_thread.packets_lb_ref = self.stream_packets_lb
        self.stream_thread.start()
        global compass
        compass = CompassSensor(pysagax.AaroniaParser())
        try:
            compass.load_calibration()
        except FileNotFoundError:
            messagebox.showerror(
                "Startup error",
                "Calibration file calibration.npz not found. Make sure sgx-pc is your workdir.",
            )

        try:
            compass.set_serial_device(
                pysagax.open_aaronia_socket_dev(f"{self.host_address.get()}:12938")
            )
        except serial.SerialException:
            self.status_compass_label.config(text="Compass sensor not connected")

        compass.start()

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
        global compass
        if compass is not None:
            compass.do_stop = True
            compass = None

    def save_octave_commands(self) -> None:
        """
        Action of the "Rec Octave" button
        """
        global compass_data
        global roi_data
        global octave_recording
        global args

        if octave_recording:
            pysagax.save_octave(
                filename=f"octave{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                variables={
                    "roi": roi_data,
                    "compass": compass_data,
                },
            )

            roi_data = np.empty([0, 2])
            compass_data = np.empty([0, 1])
            octave_recording = False
            self.save_octave_button.config(relief="raised")
            self.save_octave_button.config(
                text=f"Rec {args.rec_count}" if args.rec_count else "Rec Octave"
            )
        else:
            octave_recording = True
            self.save_octave_button.config(relief="sunken")

    def recording_sample_callback(self) -> None:
        if args.rec_count:
            if roi_data.shape[0] >= args.rec_count:
                self.save_octave_commands()
            else:
                self.save_octave_button.config(
                    text=f"Rec {roi_data.shape[0]}/{args.rec_count}"
                )
        else:
            self.save_octave_button.config(text=f"Rec {roi_data.shape[0]}")


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = ClientWindow()
    root.geometry("1024x768")
    root.wm_title("RAC Test Client")
    root.mainloop()
    ex.disconnect_commands()
