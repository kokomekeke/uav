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
import random
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
import pandas as pd

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
)

auto_test_params = {"gains": range(35, 61, 5),   #list of USPR gain levels to test
                    "freqs": [],                #TODO
                    "antenna_radii": [],        #TODO
                    "angles": [],               #TODO
                    "burst_time": 1, #length of collecting samples in seconds for each setting
                    }
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
args = parser.parse_args()
octave_recording = False

recording_sample_callback: Optional[Callable[[], None]]


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

        self.waterfall_error: Optional[WaterfallAngleGraph] = None###
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
        self.waterfall_error = WaterfallAngleGraph(
            self.waterfall_plot, self.params
        ).initialize("green", "Heading Error")  
        self.waterfall_compass = (
            WaterfallAngleGraph(self.waterfall_plot, self.params)
            .initialize("red", "Expected Heading")
            .make_plot()
        )
        self.waterfall_compass.plot.set_ylabel("")
        self.waterfall_compass.plot.yaxis.set_major_formatter(  # type: ignore
            lambda x, y: f"{float(x - self.params.waterfall_size)/float(args.fps):.2f}s"
        )
        self.df_graph = CompassGraph(self.compass_plot, self.params).initialize(
            "blue", "DF Heading"
        )

        self.compass_graph = (
            CompassGraph(self.compass_plot, self.params)
            .initialize("red", "Expected Heading")
            .make_plot()
        )
        self.graph_list = [
            graph
            for graph in [
                self.waterfall_compass,
                self.waterfall_df,
                self.waterfall_error,
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
        }

        self.connection: DfModule = DfModule(self.df_callback, self.status_callback)

        self.fig: Optional[pyplot.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.canvas_toolbar: Optional[NavigationToolbar2Tk] = None

        self.pack(fill=tkinter.BOTH, expand=1)
        self.started: bool = False

        self.gen_host_string = tkinter.StringVar(value="10.1.1.221")
        self.host_string = tkinter.StringVar(value="10.1.1.113")
        self.host_type = tkinter.StringVar(value="LENA")
        self.freq_string = tkinter.StringVar(value="300M")
        self.bw_string = tkinter.StringVar(value="300k")
        self.gain_string = tkinter.StringVar(value="8")
        self.ant_radius_string = tkinter.StringVar(value="0")
        self.angle_string = tkinter.StringVar(value="45")

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

        gen_host_label = tkinter.Label(connect_frame, text="GenHost:")
        gen_host_label.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=5, pady=10, expand=True
        )

        self.gen_host_entry = tkinter.Entry(
            connect_frame, textvariable=self.gen_host_string
        )
        self.gen_host_entry.pack(side=tkinter.LEFT, padx=5, expand=True)

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

        self.freq_combo = ttk.Combobox(control_frame, textvariable=self.freq_string)
        self.freq_combo["values"] = [
            #"32M",  #could not set gen freq error
            #"40M",
            #"48M",
            #"50M",
            #"60M",
            #"75M",  
            #"80M",
            #"96M",
            #"100M",
            #"120M",
            "150M",
            "160M",
            "200M",
            "240M",
            "300M",
            "301M",
            "400M",
            "446M",
            #"480M",    #could not set gen freq error
            "600M",
            #"800M", #no packets received
            #"1200M", #no packets received
            #"2400M", #no packets received
        ]
        self.freq_combo["state"] = "readonly"
        self.freq_combo.grid(
            column=1, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        # freq_entry = ttk.Entry(control_frame, textvariable=self.freq_string)
        # freq_entry.grid(column=1, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        bw_entry_label = ttk.Label(control_frame, text="Bandwidth:")
        bw_entry_label.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=5)

        bw_entry = ttk.Entry(control_frame, textvariable=self.bw_string)
        bw_entry.grid(column=1, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        gain_entry_label = ttk.Label(control_frame, text="USRP Gain:")
        gain_entry_label.grid(column=0, row=2, sticky=tkinter.W, padx=5, pady=5)

        gain_entry = ttk.Entry(control_frame, textvariable=self.gain_string)
        gain_entry.grid(column=1, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        self.start_stop_button = tkinter.Button(
            control_frame, text="Start", command=self.start_stop_commands
        )
        self.start_stop_button.grid(
            column=0, row=3, padx=5, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.reconf_button = tkinter.Button(
            control_frame, text="Reconf", command=self.reconf_commands
        )
        self.reconf_button.grid(
            column=1, row=3, padx=5, pady=5, sticky=tkinter.E + tkinter.W
        )

        ant_radius_entry_label = ttk.Label(control_frame, text="Antenna radius:")
        ant_radius_entry_label.grid(column=0, row=4, sticky=tkinter.W, padx=5, pady=5)

        # ant_radius_entry = ttk.Entry(control_frame, textvariable=self.ant_radius_string)
        # ant_radius_entry.grid(column=1, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        from itertools import chain

        self.ant_radius_combo = ttk.Combobox(
            control_frame, textvariable=self.ant_radius_string
        )
        self.ant_radius_list = list(
            chain.from_iterable(
                [
                    (
                        i * 0.062356831264 * math.sqrt(2) * 0.5,
                        i * 0.062356831264 * 2,
                    )
                    for i in range(12)
                ]
            )
        )
        self.ant_radius_combo["values"] = [f"{(ar*100):.2f} cm" for ar in self.ant_radius_list]

        self.ant_radius_combo["state"] = "readonly"
        self.ant_radius_combo.grid(
            column=1, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        self.ant_radius_string.trace("w", self.update_angles_list)  # type: ignore
        angle_entry_label = ttk.Label(control_frame, text="Angle (deg):")
        angle_entry_label.grid(column=0, row=5, sticky=tkinter.W, padx=5, pady=5)

        self.angle_combo = ttk.Combobox(control_frame, textvariable=self.angle_string)
        self.angle_combo["values"] = list(["0"])
        self.angle_combo["state"] = "readonly"
        self.angle_combo.grid(
            column=1, row=5, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        self.reconf_button = tkinter.Button(
            control_frame, text="Set Gen Angle", command=self.set_gen_commands
        )
        self.reconf_button.grid(
            column=1, row=6, padx=5, pady=5, sticky=tkinter.E + tkinter.W
        )

        self.auto_test_button = tkinter.Button(
            control_frame, text="Run Test Sweep", command=self.auto_test_commands
        )
        self.auto_test_button.grid(
            columnspan=2, row=8, padx=5, pady=25, sticky=tkinter.E + tkinter.W
        )

        self.recording_led = tkinter.Label(control_frame, text="   ", bg="red")
        self.recording_led.grid(
            column=1, row=9, padx=5, pady=5, sticky=tkinter.E + tkinter.W
        )

        control_frame.pack(fill=tkinter.BOTH, side=tkinter.LEFT, expand=True)

        self.heading_df_history = np.empty([0, 1])
        self.heading_angle_history = np.empty([0, 1])

        self.display_thread = DisplayThread()
        self.display_thread.recreate_canvas_action = self.create_canvas
        self.display_thread.status_label_ref = self.status_label
        self.display_thread.start()

        self.auto_test_thread = None ##
        self.auto_test_recording = False
        self.heading_angle_history

    def update_angles_list(self, *kwargs: Any) -> None:
        if self.ant_radius_combo.current() % 2 == 0:
            self.angle_combo["values"] = list([k * 90 + 45 for k in range(4)])
        else:
            self.angle_combo["values"] = list([k * 90 for k in range(4)])
        self.angle_string.set(self.angle_combo["values"][0])

    def status_callback(self, status: str) -> None:
        self.status_label.config(text=status)

    def df_callback(self, result: DfResult) -> None:
        assert self.display_thread.waterfall_compass is not None
        assert self.display_thread.compass_graph is not None
        assert self.display_thread.waterfall_df is not None
        assert self.display_thread.waterfall_error is not None
        assert self.display_thread.df_graph is not None

        expected_angle = self.angle_string.get()
        if expected_angle.isnumeric():
            numeric_expected_angle = float(expected_angle) / 180.0 * np.pi
            if numeric_expected_angle > np.pi:
                numeric_expected_angle -= 2 * np.pi
            self.display_thread.waterfall_compass.add_point(numeric_expected_angle)
            self.display_thread.compass_graph.add_point(numeric_expected_angle)
            if octave_recording or self.auto_test_recording:
                self.heading_angle_history = np.append(
                    self.heading_angle_history,
                    np.array([[numeric_expected_angle]]),
                    axis=0,
                )
        else:
            self.display_thread.waterfall_compass.add_point(None)
            self.display_thread.compass_graph.add_point(None)
            if octave_recording or self.auto_test_recording:
                self.heading_angle_history = np.append(
                    self.heading_angle_history,
                    np.array([["NaN"]]),
                    axis=0,
                )
        if not result.no_signal:
            angle_error = result.azimuth - numeric_expected_angle
            if angle_error > np.pi:                
                angle_error -= 2 * np.pi
            if angle_error < -np.pi:                
                angle_error += 2 * np.pi
            self.display_thread.waterfall_df.add_point(result.azimuth)
            self.display_thread.waterfall_error.add_point(angle_error)
            self.display_thread.df_graph.add_point(result.azimuth)
            if octave_recording or self.auto_test_recording:
                self.heading_df_history = np.append(
                    self.heading_df_history,
                    np.array([[result.azimuth]]),
                    axis=0,
                )
        else:
            self.display_thread.waterfall_df.add_point(None)
            self.display_thread.waterfall_error.add_point(None)
            self.display_thread.df_graph.add_point(None)
            if octave_recording or self.auto_test_recording:
                self.heading_df_history = np.append(
                    self.heading_df_history,
                    np.array([["NaN"]]),
                    axis=0,
                )
        if octave_recording:
            if recording_sample_callback is not None:
                recording_sample_callback()


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

    def set_params(self) -> None:
        assert isinstance(self.connection, LenaDf)
        self.connection.set_freq(pysagax.si_to_float(self.freq_string.get()))
        self.connection.set_bandwidth(pysagax.si_to_float(self.bw_string.get()))
        self.connection.gain = int(pysagax.si_to_float(self.gain_string.get()))

    def set_gen_commands(self) -> None:
        antenna_distance = self.ant_radius_combo.current() // 2
        delays = (0, 0, 0, 0)
        if self.ant_radius_combo.current() % 2 == 0:
            delays = [
                #    N  S  E  W
                (0, 1, 0, 1),
                (1, 0, 0, 1),
                (1, 0, 1, 0),
                (0, 1, 1, 0),
            ][self.angle_combo.current()]
        else:
            delays = [
                #    N  S  E  W
                (0, 2, 1, 1),
                (1, 1, 0, 2),
                (2, 0, 1, 1),
                (1, 1, 2, 0),
            ][self.angle_combo.current()]
        delays = [i * antenna_distance for i in delays]
        freq = pysagax.si_to_float(self.freq_string.get())
        import requests

        req = {
            "vcxo": 100000000,
            "mode": "default",
            "input_priority": ["pps", "ref_in", "ref_clk", "tcxo"],
            "channels": [
                {
                    "id": 1,
                    "enable": True,
                    "cmos": 0,
                    "frequency": f"{freq:.0f}",
                    "coarse_delay": delays[0],
                    "fine_delay": 0,
                },
                {
                    "id": 2,
                    "enable": True,
                    "cmos": 0,
                    "frequency": f"{freq:.0f}",
                    "coarse_delay": delays[1],
                    "fine_delay": 0,
                },
                {
                    "id": 3,
                    "enable": True,
                    "cmos": 0,
                    "frequency": f"{freq:.0f}",
                    "coarse_delay": delays[2],
                    "fine_delay": 0,
                },
                {
                    "id": 4,
                    "enable": True,
                    "cmos": 0,
                    "frequency": f"{freq:.0f}",
                    "coarse_delay": delays[3],
                    "fine_delay": 0,
                },
                {
                    "id": 5,
                    "enable": False,
                    "cmos": 3,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 6,
                    "enable": False,
                    "cmos": 3,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 7,
                    "enable": False,
                    "cmos": 3,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 8,
                    "enable": False,
                    "cmos": 3,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 9,
                    "enable": False,
                    "cmos": 0,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 10,
                    "enable": False,
                    "cmos": 0,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 11,
                    "enable": False,
                    "cmos": 0,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 12,
                    "enable": False,
                    "cmos": 0,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 13,
                    "enable": False,
                    "cmos": 0,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
                {
                    "id": 14,
                    "enable": False,
                    "cmos": 0,
                    "frequency": "10000000",
                    "coarse_delay": 0,
                    "fine_delay": 0,
                },
            ],
        }  # Making a PATCH request
        import json

        r = requests.patch(
            f"http://{self.gen_host_string.get()}:8000/synchrona/outputs",
            data=json.dumps(req),
        )

        # check status code for response received
        # success code - 200
        if r.status_code != 200:
            messagebox.showerror("Error", "Could not set generator frequency")
        errno_str = json.loads(r.content)["errno_str"]
        # print content of request
        if errno_str != "":
            messagebox.showerror("Error", errno_str)

    def auto_test_commands(self) -> None:
        #TODO: button config (disable GUI while test is running)
        self.auto_test_thread = threading.Thread(target=self.auto_test_controller)
        self.auto_test_thread.start()

    def auto_test_controller(self):
        def index_of_best_radius(rad_list, freq):       #Calculate the largest antenna radius that can be used for the given frequency
            max_radius = 3e8 / 4 / freq     #Max diameter = lambda/2 
            best_even = 0
            best_odd = 1
            for i, r in enumerate(rad_list):
                if i % 2:
                    if r < max_radius * 1 and r > rad_list[best_odd]:   ###100% of lambda/4
                        best_odd = i
                else:
                    if r < max_radius * 1 and r > rad_list[best_even]:
                        best_even = i
            return best_even, best_odd
        

        print("TEST Started")
        self.recording_led["bg"] = "orange"
        self.result_pd = pd.DataFrame(columns=["Freq", "USRP gain", "Ant radius", "Sample count", "Expected angle", "Measured mean", "Measured std dev", "RMS error"])
        
        runtime_backup_dir = "pandas_backup"
        if not os.path.exists(runtime_backup_dir):
            os.makedirs(runtime_backup_dir)

        for gain in auto_test_params["gains"]: 
            self.gain_string.set(str(gain))

            for freq in range(len(self.freq_combo['values'])):
                self.freq_combo.current(freq)
                self.reconf_commands()
                time.sleep(10)

                #radiuses_to_test = index_of_best_radius(self.ant_radius_list, pysagax.si_to_float(self.freq_string.get()))
                radiuses_to_test = [3]      # 12.47cm radius for every freq
                
                for ant_radius in radiuses_to_test:
                    self.ant_radius_combo.current(ant_radius)

                    for angle in range(len(self.angle_combo["values"])):
                        self.angle_combo.current(angle)
                        self.set_gen_commands()
                        time.sleep(1)

                        self.run_test()
                        
                        #Save results to disk after every 100 tests
                        if not len(self.result_pd.index) % 100:     
                            filename=f"{runtime_backup_dir}/time_{datetime.now().strftime('%Y%m%d_%H%M%S')}_rows0-{len(self.result_pd.index)-1}_.csv"
                            self.result_pd.to_csv(filename)

        filename=f"auto_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.result_pd.to_csv(filename)
        print("AUTO TEST FINISHED")
        self.recording_led["bg"] = "red"
    
    def run_test(self):
        self.recording_led["bg"] = "green"
        self.auto_test_recording = True
        time.sleep(auto_test_params["burst_time"])   
        self.auto_test_recording = False
        self.recording_led["bg"] = "orange"
        self.record_results()
        
    def record_results(self):
        def normalize_angle(angle):
            if angle > np.pi:                
                angle -= 2 * np.pi
            if angle < -np.pi:                
                angle += 2 * np.pi
            return angle
            
        history_pd = pd.DataFrame(data= {"df_history": np.squeeze(self.heading_df_history), "angle_history": np.squeeze(self.heading_angle_history)})        
        #heading_angle_pd = pd.DataFrame(self.heading_angle_history)

        history_pd["angle_error"] = history_pd["df_history"] - history_pd["angle_history"]
        history_pd["angle_error"] = history_pd["angle_error"].apply(func=normalize_angle)

        new_row = pd.DataFrame({"Freq": pysagax.si_to_float(self.freq_string.get()), #self.connection.freq,
                                "USRP gain": self.gain_string.get(),
                                "Ant radius": self.ant_radius_list[self.ant_radius_combo.current()],
                                "Sample count": len(np.squeeze(self.heading_df_history)),
                                "Expected angle": self.heading_angle_history[0,0] * 180/np.pi,
                                "Measured mean": history_pd["df_history"].mean() * 180/np.pi,
                                "Measured std dev": history_pd["angle_error"].std() * 180/np.pi,
                                "RMS error": ((history_pd["angle_error"] * 180/np.pi) ** 2).mean() ** 0.5}, index=[0])
        self.result_pd = pd.concat([self.result_pd, new_row], ignore_index=True)
        print(self.result_pd)
        print("df_std_dev:", history_pd["df_history"].std() * 180/np.pi,
              "error_std_dev:", history_pd["angle_error"].std() * 180/np.pi,
              "difference:", history_pd["df_history"].std()*180/np.pi - history_pd["angle_error"].std()*180/np.pi) ###

        self.heading_df_history = np.empty([0, 1])
        self.heading_angle_history = np.empty([0, 1])
                        

    def start_commands(self) -> None:
        self.set_params()
        self.connection.start_measurement()

    def stop_commands(self) -> None:
        self.connection.stop_measurement()

    def reconf_commands(self) -> None:
        assert isinstance(self.connection, LenaDf)
        self.set_params()
        self.connection.send_command(
            f"SOURCE:CenterFrequency! {self.connection.freq:.0f};"
            f"SOURCE:ChannelGain! 0 {self.connection.gain};"
            f"SOURCE:ChannelGain! 1 {self.connection.gain};"
            f"SOURCE:ChannelGain! 2 {self.connection.gain};"
            f"SOURCE:ChannelGain! 3 {self.connection.gain};"
            f"SOURCE:Configure!;"
            f"AOA:Configure!;"
            f"ROI:Enable! 1;"
            f"ROI:Span! 50000;"
            f"ROI:Threshold! -60;"
            f"ROI:CenterFrequency! {self.connection.roi_freq:.0f};"
            f"ROI:Configure!;"
        ) ###TODO: ROI span and ROI threshold was changed to 50k and -60 for reconf command. This should be implemented for start command as well.

    def start_stop_commands(self) -> None:
        if self.started:
            self.stop_commands()
            self.started = False
            self.start_stop_button.config(text="Start")
        else:
            self.start_commands()
            self.started = True
            self.start_stop_button.config(text="Stop")

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
                    "ahrs": self.heading_angle_history,
                },
            )

            self.heading_df_history = np.empty([0, 1])
            self.heading_angle_history = np.empty([0, 1])
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


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = ClientWindow()
    root.geometry("1024x768")
    root.wm_title("Automatic LENA Tester")
    root.mainloop()
    ex.disconnect_commands()
