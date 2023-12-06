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
    DfModule,
    DfResult,
    LenaDf,
    CompassGraph,
    DDF260,
)

parser = argparse.ArgumentParser(description="CS Test client parameters")
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
parser.add_argument(
    "--fs",
    metavar="N",
    type=int,
    default=25,
    help="compass sensor sampling rate",
)
args = parser.parse_args()
octave_recording = False


class DisplayThread(threading.Thread):
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

        self.waterfall_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the waterfall plot
        """

        self.waterfall_df: Optional[WaterfallAngleGraph] = None
        """
        Matplotlib image object for the compass sensor waterfall
        """

        self.waterfall_compass: Optional[WaterfallAngleGraph] = None
        """
        Matplotlib image object for the compass sensor waterfall
        """

        self.compass_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the waterfall plot
        """

        self.compass_graph: Optional[CompassGraph] = None
        """
        Matplotlib image object for the compass sensor waterfall
        """

        self.compass_heading_graph: Optional[CompassGraph] = None
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

        self.recreate_canvas_action: Optional[Callable[[], None]] = None
        """
        Action that recreates plot canvas
        """

        self.disconnect: bool = False
        """
        When the disconnect flag is set, the thread loop will quit on the next iteration.
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

        # The code below will handle the preprocessed packets from the stream process
        self.create_anim()
        self.animation_started = True
        while not self.disconnect:
            # self.read_from_compass_sensor()
            time.sleep(1)

        self.animation_started = False

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
            nrows=2, ncols=1, height_ratios=(1, 1)
        )
        self.waterfall_plot = self.fig_ref.add_subplot(grid_spec[0, 0])
        self.compass_plot = self.fig_ref.add_subplot(
            grid_spec[1, 0], projection="polar"
        )
        self.waterfall_df = WaterfallAngleGraph(
            self.waterfall_plot, self.params
        ).initialize("blue", "DF Heading")
        self.waterfall_compass = (
            WaterfallAngleGraph(self.waterfall_plot, self.params)
            .initialize("red", "AHRS Heading")
            .make_plot()
        )
        self.waterfall_compass.plot.set_ylabel("")
        self.waterfall_compass.plot.yaxis.set_major_formatter(  # type: ignore
            lambda x, y: f"{float(x - self.params.waterfall_size)/float(args.fs):.2f}s"
        )
        self.df_graph = CompassGraph(self.compass_plot, self.params).initialize(
            "blue", "DF Heading"
        )

        self.compass_graph = (
            CompassGraph(self.compass_plot, self.params)
            .initialize("red", "AHRS Heading")
            .make_plot()
        )
        self.graph_list = [
            graph
            for graph in [
                self.waterfall_compass,
                self.waterfall_df,
                self.compass_graph,
                self.compass_heading_graph,
                self.df_graph,
            ]
            if graph is not None
        ]
        self.animation = FuncAnimation(
            self.fig_ref,
            self.update_imag,
            interval=int(1000 / args.fps),
            blit=True,
            cache_frame_data=False,
        )

        grid_spec.tight_layout(figure=self.fig_ref)
        grid_spec.update()

        self.fig_ref.canvas.draw()  # type: ignore


class ClientWindow(tkinter.Frame):
    def __init__(self) -> None:
        global args
        super().__init__()

        self.supported_host_types: dict[str, typing.Type[DfModule]] = {
            "LENA": LenaDf,
            "DDF260": DDF260,
        }

        self.connection: DfModule = DfModule(self.df_callback, self.status_callback)

        self.fig: Optional[pyplot.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.canvas_toolbar: Optional[NavigationToolbar2Tk] = None

        self.pack(fill=tkinter.BOTH, expand=1)

        self.host_string = tkinter.StringVar(value="localhost")
        self.host_type = tkinter.StringVar(value="LENA")
        self.freq_string = tkinter.StringVar(value="300M")
        self.bw_string = tkinter.StringVar(value="300k")

        # ## STATUS FRAME

        status_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        status_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        status_label_label = tkinter.Label(
            status_frame,
            text="Status:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_label = tkinter.Label(
            status_frame, text="Not connected", font=tkinter.font.Font(size=10)
        )
        self.status_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        # ## CONNECT FRAME

        connect_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        connect_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        self.save_octave_button = tkinter.Button(
            connect_frame, text="Rec Octave", command=self.save_octave_commands
        )
        self.save_octave_button.pack(side=tkinter.LEFT)
        host_command_label = tkinter.Label(connect_frame, text="Host:")
        host_command_label.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=5, pady=10, expand=True
        )

        self.host_entry = tkinter.Entry(connect_frame, textvariable=self.host_string)
        self.host_entry.pack(side=tkinter.LEFT, padx=5, expand=True)

        self.type_combo = ttk.Combobox(connect_frame, textvariable=self.host_type)
        self.type_combo["values"] = list(self.supported_host_types.keys())
        self.type_combo["state"] = "readonly"
        self.type_combo.pack(side=tkinter.LEFT, padx=5, expand=True)
        self.disconnect_button = tkinter.Button(
            connect_frame, text="Disconnect", command=self.disconnect_commands
        )
        self.disconnect_button.pack(side=tkinter.RIGHT, padx=5, pady=5)
        self.disconnect_button.configure(state="disabled")

        self.connect_button = tkinter.Button(
            connect_frame, text="Connect", command=self.connect_commands
        )
        self.connect_button.pack(side=tkinter.RIGHT)

        # ## MAIN FRAME

        main_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        main_frame.pack(fill=tkinter.BOTH, side=tkinter.TOP, expand=True)
        self.plot_frame = tkinter.Frame(main_frame)
        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.RIGHT)

        # ## CONTROL FRAME

        control_frame = tkinter.Frame(main_frame, relief=tkinter.RAISED, borderwidth=1)
        # control_frame.configure(background='red')

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
            column=1, row=2, padx=5, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.stop_button = tkinter.Button(
            control_frame, text="Stop", command=self.stop_commands
        )
        self.stop_button.grid(
            column=0, row=2, padx=5, pady=5, sticky=tkinter.E + tkinter.W
        )

        control_frame.pack(fill=tkinter.BOTH, side=tkinter.LEFT, expand=True)

        self.heading_df_history = np.empty([0, 1])
        self.heading_ahrs_history = np.empty([0, 1])

        self.compass: Optional[CompassSensor] = None

        if args.sensor_dev or args.aaronia:
            self.compass = CompassSensor(
                pysagax.AaroniaParser() if args.aaronia else pysagax.SimpleParser(),
            )
            try:
                self.compass.load_calibration()
            except FileNotFoundError:
                messagebox.showerror(
                    "Startup error",
                    "Calibration file calibration.npz not found. Make sure sgx-pc is your workdir.",
                )

            try:
                self.compass.set_serial_device(
                    pysagax.open_aaronia_serial_dev()
                    if args.aaronia
                    else pysagax.open_arduino_serial_dev(args.sensor_dev)
                )
            except serial.SerialException:
                messagebox.showerror(
                    "Startup error",
                    "Compass sensor not connected. Make sure it is turned on.",
                )

            self.compass.start()

        self.display_thread = DisplayThread()
        self.display_thread.recreate_canvas_action = self.create_canvas
        self.display_thread.status_label_ref = self.status_label
        self.display_thread.start()

    def status_callback(self, status: str) -> None:
        self.status_label.config(text=status)

    def df_callback(self, result: DfResult) -> None:
        if self.compass is not None:
            self.display_thread.waterfall_compass.add_point(self.compass.angle)
            self.display_thread.compass_graph.add_point(self.compass.angle)
            if octave_recording:
                self.heading_ahrs_history = np.append(
                    self.heading_ahrs_history,
                    np.array([[self.compass.angle]]),
                    axis=0,
                )
        else:
            self.display_thread.waterfall_compass.add_point(None)
            self.display_thread.compass_graph.add_point(None)
            if octave_recording:
                self.heading_ahrs_history = np.append(
                    self.heading_ahrs_history,
                    np.array([["NaN"]]),
                    axis=0,
                )
        if not result.no_signal:
            self.display_thread.waterfall_df.add_point(result.azimuth)
            self.display_thread.df_graph.add_point(result.azimuth)
            if octave_recording:
                self.heading_df_history = np.append(
                    self.heading_df_history,
                    np.array([[result.azimuth]]),
                    axis=0,
                )
        else:
            self.display_thread.waterfall_df.add_point(None)
            self.display_thread.df_graph.add_point(None)
            if octave_recording:
                self.heading_df_history = np.append(
                    self.heading_df_history,
                    np.array([["NaN"]]),
                    axis=0,
                )

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
        self.canvas_toolbar.pack(side=tkinter.BOTTOM, fill=tkinter.X, expand=False)
        if self.display_thread is not None:
            self.display_thread.fig_ref = self.fig

    def start_commands(self) -> None:
        self.connection.set_freq(pysagax.si_to_float(self.freq_string.get()))
        self.connection.set_bandwidth(pysagax.si_to_float(self.bw_string.get()))
        self.connection.start_measurement()

    def stop_commands(self) -> None:
        self.connection.stop_measurement()

    def connect_commands(self) -> None:
        """
        Action of the "Connect" button
        """
        conn_class = self.supported_host_types[self.host_type.get()]
        self.connection = conn_class(self.df_callback, self.status_callback)
        self.connection.status_callback = self.status_callback
        self.connection.df_callback = self.df_callback
        self.connection.connect(self.host_string.get())
        self.connect_button.configure(state="disabled")
        self.host_entry.configure(state="disabled")
        self.disconnect_button.configure(state="normal")

    def save_octave_commands(self) -> None:
        """
        Action of the "Rec Octave" button
        """
        global octave_recording

        if octave_recording:
            pysagax.save_octave(
                filename=f"octave{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                variables={
                    "df": self.heading_df_history,
                    "ahrs": self.heading_ahrs_history,
                },
            )

            self.heading_df_history = np.empty([0, 1])
            self.heading_ahrs_history = np.empty([0, 1])
            octave_recording = False
            self.save_octave_button.config(relief="raised")
        else:
            octave_recording = True
            self.save_octave_button.config(relief="sunken")

    def disconnect_commands(self) -> None:
        """
        Action of the "Disconnect" button
        """
        self.connection.disconnect()
        self.display_thread.disconnect = True
        try:
            self.disconnect_button.configure(state="disabled")
            self.host_entry.configure(state="normal")
            self.connect_button.configure(state="normal")
        except tkinter.TclError:
            pass


def main() -> None:
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = ClientWindow()
    root.geometry("1024x768")
    root.wm_title("DF Client")
    root.mainloop()
    ex.disconnect_commands()


if __name__ == "__main__":
    main()
