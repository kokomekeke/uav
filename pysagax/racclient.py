#!/usr/bin/env python3

from __future__ import annotations

import argparse
import collections
import math
import multiprocessing
import os
import queue
import re
import socket
import threading
import time
import tkinter

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import traceback
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from time import sleep
from tkinter import font  # #why this it needed?
from tkinter import ttk
from typing import Any, Callable, Literal, Optional

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import pyplot
from matplotlib.animation import FuncAnimation  # type: ignore
from matplotlib.backend_bases import KeyEvent  # type: ignore
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_tkagg import (  # type: ignore
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)
import scipy

import pysagax
from pysagax import (
    BaseConnection,
    CompassGraph,
    CompassGraphWithDeviation,
    CoreServiceDebugPacket,
    CoreServiceEOFPacket,
    CoreServicePacket,
    CoreServiceROILackOfSignalPacket,
    CoreServiceROIResultPacket,
    CoreServiceSpectrumPacket,
    GraphParameters,
    MagnitudeSpectrumGraph,
    MultiQueue,
    StreamAndCompassProcess,
    WaterfallAngleGraph,
    WaterfallMagnitudeGraph,
)
from pysagax.ui.sgx_dfg_map_server import DFGMapServer

conf = None


def en_if(cond: bool) -> Literal["normal", "active", "disabled"]:
    if cond:
        return "normal"
    else:
        return "disabled"


def calculate_df_corrected(df_value, compass_heading, encoder_heading):
    df_corrected_from_compass = (
        conf["defaults"]["df_corrected_from_compass"] if conf else True
    )
    df_corrected = None
    if df_value is not None:
        if df_corrected_from_compass and compass_heading is not None:
            df_corrected = pysagax.normalize_angle(compass_heading + df_value)
        if not df_corrected_from_compass and encoder_heading is not None:
            df_corrected = pysagax.normalize_angle(encoder_heading + df_value)
    return df_corrected


###TODO:REMOVE
class ExapmleFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client = self.master.client  ##???


class ConnectFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client = self.master.client  ##???

        compass_offset = -1  ##TODO: should be an argument of master.client?
        encoder_offset = np.pi  ##TODO: should be an argument of master.client?

        self.host_address = tkinter.StringVar(
            value=(conf["defaults"]["host"] if conf else "")
        )
        self.encoder_port_string = tkinter.StringVar(
            value=(conf["defaults"]["encoder_port"] if conf else "")
        )

        offset_frame = tkinter.Frame(
            self,
        )
        offset_frame.pack(
            fill=tkinter.BOTH, expand=False, side=tkinter.LEFT, pady=0, padx=(20, 0)
        )
        compass_offset_label_label = tkinter.Label(
            offset_frame, text="Compass offset: ", font=tkinter.font.Font(size=8)
        )
        compass_offset_label_label.grid(column=0, row=0, pady=0)
        self.compass_offset_label = tkinter.Label(
            offset_frame,
            text=f"{(compass_offset * 180 / np.pi):.2f}°",
            font=tkinter.font.Font(size=8),
        )
        self.compass_offset_label.grid(column=1, row=0, pady=0)
        encoder_offset_label_label = tkinter.Label(
            offset_frame, text="Encoder offset: ", font=tkinter.font.Font(size=8)
        )
        encoder_offset_label_label.grid(column=0, row=1, pady=0)
        self.encoder_offset_label = tkinter.Label(
            offset_frame,
            text=f"{(encoder_offset * 180 / np.pi):.2f}°",
            font=tkinter.font.Font(size=8),
        )
        self.encoder_offset_label.grid(column=1, row=1, pady=0)

        self.set_offset_button = tkinter.Button(
            self, text="Set offsets", command=self.set_offsets
        )
        self.set_offset_button.pack(side=tkinter.LEFT)

        host_label = tkinter.Label(self, text="Spectrum channel:")
        host_label.pack(
            side=tkinter.LEFT, fill=tkinter.NONE, padx=(20, 5), pady=10, expand=False
        )

        # self.channel_spectrum_combo_string =
        self.channel_spectrum_combo = ttk.Combobox(self, width=1)
        self.channel_spectrum_combo["values"] = [0, 1, 2, 3]
        self.channel_spectrum_combo.pack(side=tkinter.LEFT)
        self.channel_spectrum_combo.bind(
            "<<ComboboxSelected>>", self.choose_spectrum_commands
        )
        self.channel_spectrum_combo.configure(state="disabled")

        host_label = tkinter.Label(self, text="Host:")
        host_label.pack(
            side=tkinter.LEFT, fill=tkinter.NONE, padx=(60, 5), pady=10, expand=False
        )

        self.host_entry = tkinter.Entry(self, textvariable=self.host_address, width=15)
        self.host_entry.pack(side=tkinter.LEFT, padx=5, expand=False)

        encoder_port_label = tkinter.Label(self, text="Encoder port:")
        encoder_port_label.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=(10, 5), pady=10, expand=False
        )

        self.encoder_port_entry = tkinter.Entry(
            self, textvariable=self.encoder_port_string, width=8
        )
        self.encoder_port_entry.pack(side=tkinter.LEFT, padx=5, expand=False)

        self.disconnect_button = tkinter.Button(
            self, text="Disconnect", command=self.master.disconnect_commands
        )
        self.disconnect_button.pack(side=tkinter.RIGHT, padx=5, pady=5)
        self.disconnect_button.configure(state="disabled")

        self.connect_button = tkinter.Button(
            self, text="Connect", command=self.master.connect_commands
        )
        self.connect_button.pack(side=tkinter.RIGHT)

    def set_offsets(self):
        pass  # TODO

    def choose_spectrum_commands(self, event):
        self.client.send_commands(
            f"DEBUG:SpectrumChannel! {self.channel_spectrum_combo.current()};"
        )


class StatusFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.status_command_string = tkinter.StringVar(value="Not connected")
        self.status_stream_string = tkinter.StringVar(value="Not connected")
        self.status_compass_string = tkinter.StringVar(value="Not connected")
        self.status_map_server_string = tkinter.StringVar(value="Down")

        status_command_label_label = tkinter.Label(
            self,
            text="Command:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_command_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_command_label = tkinter.Label(
            self,
            textvariable=self.status_command_string,
            font=tkinter.font.Font(size=10),
        )
        self.status_command_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_stream_label_label = tkinter.Label(
            self,
            text="Stream:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_stream_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_stream_label = tkinter.Label(
            self,
            textvariable=self.status_stream_string,
            font=tkinter.font.Font(size=10),
        )
        self.status_stream_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_compass_label_label = tkinter.Label(
            self,
            text="GPS/Compass:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_compass_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_compass_label = tkinter.Label(
            self,
            textvariable=self.status_compass_string,
            font=tkinter.font.Font(size=10),
        )
        self.status_compass_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_map_server_label_label = tkinter.Label(
            self,
            text="Map server:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_map_server_label_label.pack(
            side=tkinter.LEFT, padx=5, pady=10, anchor="w"
        )

        self.status_map_server_label = tkinter.Label(
            self,
            textvariable=self.status_map_server_string,
            font=tkinter.font.Font(size=10),
        )
        self.status_map_server_label.pack(
            side=tkinter.LEFT, padx=5, pady=10, anchor="w"
        )


class ControlFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client: Client = self.master.master.client  ##???

        ###TODO here or in ClientWindow???
        self.freq_string = tkinter.StringVar(
            value=(conf["defaults"]["center_freq"] if conf else "")
        )
        self.bw_string = tkinter.StringVar(
            value=(conf["defaults"]["bandwith"] if conf else "")
        )
        self.gain_string = tkinter.StringVar(
            value=(conf["defaults"]["gain"] if conf else "")
        )
        self.bin_count_string = tkinter.StringVar(
            value=(conf["defaults"]["bin_count"] if conf else "")
        )
        self.burst_stride_string = tkinter.StringVar(
            value=(conf["defaults"]["burst_stride"] if conf else "")
        )
        self.roi_center_string = tkinter.StringVar(
            value=(conf["defaults"]["roi_center"] if conf else "")
        )
        self.roi_span_string = tkinter.StringVar(
            value=(conf["defaults"]["roi_span"] if conf else "")
        )
        self.roi_threshold_string = tkinter.StringVar(
            value=(conf["defaults"]["roi_threshold"] if conf else "")
        )
        self.source_file_path_string = tkinter.StringVar(value="")

        self.mean_window_width_slider_variable = tkinter.DoubleVar(
            value=conf["stats"]["mean_window_width_seconds"] if conf else 0
        )

        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=2)
        self.columnconfigure(3, weight=1)

        freq_entry_label = ttk.Label(self, text="Frequency:")
        freq_entry_label.grid(column=0, row=0, sticky=tkinter.W, padx=5, pady=5)

        self.freq_entry = ttk.Entry(self, textvariable=self.freq_string, width=11)
        self.freq_entry.grid(
            column=1, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        bw_entry_label = ttk.Label(self, text="Bandwidth:")
        bw_entry_label.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=5)

        self.bw_entry = ttk.Entry(self, textvariable=self.bw_string, width=11)
        self.bw_entry.grid(
            column=1, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        gain_entry_label = ttk.Label(self, text="USRP Gain:")
        gain_entry_label.grid(column=0, row=2, sticky=tkinter.W, padx=5, pady=5)

        self.gain_entry = ttk.Entry(self, textvariable=self.gain_string, width=11)
        self.gain_entry.grid(
            column=1, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        bin_count_entry_label = ttk.Label(
            self, text="Bin count:"
        )  # TODO:separate bin count and burst stride setting?
        bin_count_entry_label.grid(column=0, row=3, sticky=tkinter.W, padx=5, pady=5)

        bin_count_combo = ttk.Combobox(
            self, textvariable=self.bin_count_string, width=11
        )
        bin_count_combo["values"] = [
            # Virgin monetary scale values.
            200,
            500,
            1000,
            2000,
            5000,
            10000,
            # Chad power of 2 values.
            0x80,
            0x100,
            0x200,
            0x400,
            0x800,
            0x1000,
            0x2000,
            0x4000,
            0x8000,
            0x10000,
            0x20000,
            0x40000,
            0x80000,
        ]
        bin_count_combo.grid(
            column=1, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        roi_center_entry_label = ttk.Label(self, text="ROI center freq:")
        roi_center_entry_label.grid(column=2, row=0, sticky=tkinter.W, padx=5, pady=5)

        roi_center_entry = ttk.Entry(
            self, textvariable=self.roi_center_string, width=11
        )
        roi_center_entry.grid(
            column=3, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        roi_span_entry_label = ttk.Label(self, text="ROI span:")
        roi_span_entry_label.grid(column=2, row=1, sticky=tkinter.W, padx=5, pady=5)

        roi_span_entry = ttk.Entry(self, textvariable=self.roi_span_string, width=11)
        roi_span_entry.grid(
            column=3, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        roi_threshold_entry_label = ttk.Label(self, text="ROI threshold")
        roi_threshold_entry_label.grid(
            column=2, row=2, sticky=tkinter.W, padx=5, pady=5
        )

        roi_threshold_entry = ttk.Entry(
            self, textvariable=self.roi_threshold_string, width=11
        )
        roi_threshold_entry.grid(
            column=3, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        burst_stride_entry_label = ttk.Label(self, text="Burst stride:")
        burst_stride_entry_label.grid(column=2, row=3, sticky=tkinter.W, padx=5, pady=5)

        burst_stride_entry = ttk.Entry(
            self, textvariable=self.burst_stride_string, width=11
        )
        burst_stride_entry.grid(
            column=3, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        self.source_combo = ttk.Combobox(self, width=12)
        self.source_combo["values"] = ["USRP", "Generator", "Recording"]
        self.source_combo.current(0)
        self.source_combo.grid(
            column=0, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )
        self.source_combo.bind("<<ComboboxSelected>>", self.source_combo_update)

        self.source_file_path_combo = ttk.Combobox(
            self, textvariable=self.source_file_path_string, width=11, state="disabled"
        )
        self.source_file_path_combo.grid(
            column=1, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5, columnspan=3
        )

        self.mean_window_width_slider = tkinter.Scale(
            self,
            from_=0,
            to=10,
            variable=self.mean_window_width_slider_variable,
            resolution=0.1,
            orient=tkinter.HORIZONTAL,
            command=self.mean_window_width_slider_commands,
        )
        self.mean_window_width_slider.grid(
            column=0, row=5, sticky=tkinter.E + tkinter.W, padx=5, pady=5, columnspan=2
        )

        self.configure_button = tkinter.Button(
            self, text="Configure", command=self.configure_commands
        )
        self.configure_button.grid(
            column=3, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.configure_button.configure(state="disabled")

    def configure_commands(self):
        default_source_file_path = "/home/sagax/Generator/"
        if self.source_combo.current() == 1:
            source_file_path = default_source_file_path
        else:
            source_file_path = self.source_file_path_string.get()

        kwargs = {
            "freq": pysagax.si_to_float(self.freq_string.get()),
            "bw": pysagax.si_to_float(self.bw_string.get()),
            "gain": self.gain_string.get(),
            "bin_count": self.bin_count_string.get(),
            "burst_stride": self.burst_stride_string.get(),
            "roi_center": pysagax.si_to_float(self.roi_center_string.get()),
            "roi_span": pysagax.si_to_float(self.roi_span_string.get()),
            "roi_threshold": self.roi_threshold_string.get(),
            "from_file": self.source_combo.current() != 0,
            "source_file_path": source_file_path,
        }
        self.client.do_configuration(**kwargs)

    def source_combo_update(self, event):
        if self.source_combo.current() == 0:
            self.freq_entry.config(state="enabled")
            self.bw_entry.config(state="enabled")
            self.gain_entry.config(state="enabled")
        else:
            self.freq_entry.config(state="disabled")
            self.bw_entry.config(state="disabled")
            self.gain_entry.config(state="disabled")

        if self.source_combo.current() == 2:
            self.source_file_path_combo.config(state="enabled")
        else:
            self.source_file_path_combo.config(state="disabled")

    def mean_window_width_slider_commands(self, event):
        window_size = self.mean_window_width_slider_variable.get()
        self.client.mean_window_width_value.value = window_size


class StatFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client = self.master.master.client  ##???

        self.df_value_string = tkinter.StringVar(value="NaN")
        self.df_value_mean_string = tkinter.StringVar(value="NaN")
        self.df_value_deviation_string = tkinter.StringVar(value="NaN")
        # self.df_value_rms_string = tkinter.StringVar(value="NaN")
        self.df_elev_string = tkinter.StringVar(value="NaN")
        self.df_elev_mean_string = tkinter.StringVar(value="NaN")
        self.df_elev_deviation_string = tkinter.StringVar(value="NaN")

        self.quality_value_string = tkinter.StringVar(value="NaN")
        self.snr_string = tkinter.StringVar(value="NaN")

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)

        disp_font = tkinter.font.Font(family="serif", size=14)

        angle_label = ttk.Label(self, text="angle:")
        angle_label.grid(column=1, row=0, sticky=tkinter.W, padx=5, pady=5)
        mean_label = ttk.Label(self, text="mean:")
        mean_label.grid(column=2, row=0, sticky=tkinter.W, padx=5, pady=5)
        deviation_label = ttk.Label(self, text="deviation:")
        deviation_label.grid(column=3, row=0, sticky=tkinter.W, padx=5, pady=5)

        df_value_label = ttk.Label(self, text="DF angle:")
        df_value_label.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=5)
        df_value_disp = ttk.Label(
            self,
            textvariable=self.df_value_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        df_value_disp.grid(
            column=1, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )
        df_value_mean_disp = ttk.Label(
            self,
            textvariable=self.df_value_mean_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        df_value_mean_disp.grid(
            column=2, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )
        df_value_deviation_disp = ttk.Label(
            self,
            textvariable=self.df_value_deviation_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        df_value_deviation_disp.grid(
            column=3, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        df_elev_label = ttk.Label(self, text="DF elevation:")
        df_elev_label.grid(column=0, row=2, sticky=tkinter.W, padx=5, pady=5)
        df_elev_disp = ttk.Label(
            self,
            textvariable=self.df_elev_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        df_elev_disp.grid(column=1, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=3)
        df_elev_mean_disp = ttk.Label(
            self,
            textvariable=self.df_elev_mean_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        df_elev_mean_disp.grid(
            column=2, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )
        df_elev_deviation_disp = ttk.Label(
            self,
            textvariable=self.df_elev_deviation_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        df_elev_deviation_disp.grid(
            column=3, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        quality_value_label = ttk.Label(self, text="Signal quality:")
        quality_value_label.grid(column=0, row=3, sticky=tkinter.W, padx=5, pady=5)
        quality_value_disp = ttk.Label(
            self,
            textvariable=self.quality_value_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        quality_value_disp.grid(
            column=1, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )
        
        snr_label = ttk.Label(self, text="SNR:")
        snr_label.grid(column=2, row=3, sticky=tkinter.W, padx=5, pady=5)
        snr_disp = ttk.Label(
            self,
            textvariable=self.snr_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        snr_disp.grid(
            column=3, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        self.peak_chart = tkinter.Canvas(
            self,
            bg="white",
            bd=0,
            highlightthickness=2,
            highlightbackground="black",
            height=59,
        )
        self.peak_chart.grid(
            column=0, row=4, columnspan=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )
        self.peak_bars = [
            self.peak_chart.create_rectangle(2, 2, 100, 14, fill="yellow"),
            self.peak_chart.create_rectangle(2, 17, 100, 29, fill="dodger blue"),
            self.peak_chart.create_rectangle(2, 32, 100, 44, fill="green"),
            self.peak_chart.create_rectangle(2, 47, 100, 59, fill="red"),
        ]
        self.peak_texts = [
            self.peak_chart.create_text(
                30, 8, text="32555", fill="black", font=("Helvetica 7 bold")
            ),
            self.peak_chart.create_text(
                30, 23, text="32555", fill="black", font=("Helvetica 7 bold")
            ),
            self.peak_chart.create_text(
                30, 38, text="32555", fill="black", font=("Helvetica 7 bold")
            ),
            self.peak_chart.create_text(
                30, 53, text="32555", fill="black", font=("Helvetica 7 bold")
            ),
        ]

    def update_peak_plot(self, peaks: list) -> None:
        """
        Updates the bar plots for peak values.
        """
        max_width = self.peak_chart.winfo_width()
        adc_resolution = 2**15 - 1

        peaks = [int(peak) for peak in peaks]
        peaks_dbfs = [
            20 * math.log10(peak / adc_resolution) if peak > 0 else float("-inf")
            for peak in peaks
        ]
        min_dbfs_level = 20 * math.log10(
            400 / adc_resolution
        )  # min value of the scale (aprox. noise level)
        bar_widths = [
            2 + (1 - peak / min_dbfs_level) * (max_width - 4)
            if peak != float("-inf")
            else 0
            for peak in peaks_dbfs
        ]  # logarithmic scaling

        self.peak_chart.coords(self.peak_bars[0], 2, 2, bar_widths[0], 14)
        self.peak_chart.coords(self.peak_bars[1], 2, 17, bar_widths[1], 29)
        self.peak_chart.coords(self.peak_bars[2], 2, 32, bar_widths[2], 44)
        self.peak_chart.coords(self.peak_bars[3], 2, 47, bar_widths[3], 59)

        for i in range(4):
            text = re.sub(
                r"^-(0\.?0*)$", r"\1", f"{peaks_dbfs[i]:.0f}"
            )  # formatting numbers rounded to -0 to +0
            self.peak_chart.itemconfig(self.peak_texts[i], text=text)

    def update_stats(self, latest_roi_results, aggregated_roi_results):
        rad_to_deg = lambda x: pysagax.normalize_angle(
            x * 180 / np.pi, high=360.0, low=0.0
        )

        self.df_value_string.set(f"{rad_to_deg(latest_roi_results['df_value']):.2f}°")
        self.df_value_mean_string.set(
            f"{rad_to_deg(aggregated_roi_results['df_value_mean']):.2f}°"
        )
        self.df_value_deviation_string.set(
            f"{rad_to_deg(aggregated_roi_results['df_value_std']):.2f}°"
        )

        self.df_elev_string.set(
            f"{rad_to_deg(latest_roi_results['df_elevation']):.2f}°"
        )
        self.df_elev_mean_string.set(
            f"{rad_to_deg(aggregated_roi_results['df_elevation_mean']):.2f}°"
        )
        self.df_elev_deviation_string.set(
            f"{rad_to_deg(aggregated_roi_results['df_elevation_std']):.2f}°"
        )


class PlotFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client: Client = self.master.client  ##???

        self.root: Any = None

        self.fig: Optional[pyplot.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.canvas_toolbar: Optional[NavigationToolbar2Tk] = None

        self.params = GraphParameters()
        # self.params.waterfall_size = args.wf    #Amount of spectrum lines to be displayed on the waterfall diagram.
        self.params.waterfall_size = 200  ##TODO: get from params

        self.animation: Optional[matplotlib.animation.FuncAnimation] = None
        """
        Matplotlib FuncAnimation object for animating the graphs
        """

        self.animation_started: bool = False
        """
        Indicates whether the animation and plot objects have been created
        """

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
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(
            side=tkinter.TOP, fill=tkinter.BOTH, expand=True
        )

        self.canvas_toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.canvas_toolbar.update()

        self.root.update()  # this solves matplotlib artifacts?

        def on_canvas_key_press(event: KeyEvent) -> None:
            key_press_handler(event, self.canvas, self.canvas_toolbar)

        self.canvas.mpl_connect("key_press_event", on_canvas_key_press)
        self.canvas_toolbar.pack(side=tkinter.TOP, fill=tkinter.X, expand=False)

        ##TODO: communicate through Client()
        # if self.stream_thread is not None:
        #     self.stream_thread.fig_ref = self.fig
        self.fig_ref = self.fig

    def create_anim(self) -> None:
        """
        Creates matplotlib animation on the GUI
        """
        self.create_canvas()

        assert self.fig_ref
        self.fig_ref.clf()

        grid_spec = self.fig_ref.add_gridspec(  # type: ignore
            nrows=2, ncols=2, width_ratios=(3, 2), height_ratios=(1, 1)
        )
        self.magnitude_waterfall_plot = self.fig_ref.add_subplot(grid_spec[1, 0])
        self.magnitude_waterfall_graph = WaterfallMagnitudeGraph(
            self.magnitude_waterfall_plot, self.params
        )
        self.magnitude_waterfall_graph.max_points = (
            conf["display"]["max_bin_count"] if conf else 1024
        )
        self.magnitude_waterfall_graph.initialize()

        # colorbar = self.fig_ref.colorbar(  # type: ignore
        #     self.magnitude_waterfall_graph.image, format=lambda x, _: f"{x:.0f}dB"
        # )     #TODO:show colorbar but keep waterfall and spectrum graphs the same width
        self.magnitude_waterfall_graph.make_plot()

        self.magnitude_spectrum_plot = self.fig_ref.add_subplot(grid_spec[0, 0])
        self.magnitude_spectrum_graph = MagnitudeSpectrumGraph(
            self.magnitude_spectrum_plot, self.params
        )
        self.magnitude_spectrum_graph.vmin = (
            conf["display"]["spectrum_graph_min_db"] if conf else -120
        )
        self.magnitude_spectrum_graph.initialize(color="blue").make_plot()

        self.fig_ref.canvas.callbacks.connect("button_press_event", self.click_handler)  # type: ignore

        self.compass_plot = self.fig_ref.add_subplot(
            grid_spec[1, 1], projection="polar"
        )
        self.df_plot = self.fig_ref.add_subplot(grid_spec[0, 1], projection="polar")

        self.df_graph = (
            CompassGraphWithDeviation(self.df_plot, self.params)
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

        self.encoder_graph = CompassGraph(self.compass_plot, self.params).initialize(
            "green", "Encoder Heading"
        )

        self.compass_plot.legend(loc="upper left", bbox_to_anchor=(1, 1.1))
        self.df_plot.legend(loc="upper left", bbox_to_anchor=(1, 1))

        self.graph_list = [
            graph
            for graph in [
                self.magnitude_waterfall_graph,
                self.magnitude_spectrum_graph,
                self.df_graph,
                self.compass_graph,
                self.compass_df_graph,
                self.encoder_graph,
            ]
            if graph is not None
        ]

        fps = conf["display"]["fps"] if conf else 25
        self.animation = FuncAnimation(
            self.fig_ref, self.update_imag, interval=int(1000 / fps), blit=True
        )

        grid_spec.tight_layout(figure=self.fig_ref)
        grid_spec.update()
        # self.fig_ref.canvas.draw()  # type: ignore

    def update_imag(self, frame_number: int) -> list[matplotlib.artist.Artist]:
        self.update_sensors_and_graphs()
        image_list = []
        for graph in self.graph_list:
            graph.update()
            image_list.extend(graph.collect_images())
        return image_list

    def click_handler(self, event: Any) -> None:
        if self.master.status_frame.status_command_string.get() != "Connected":
            return
        control_frame_ref = self.master.control_frame  ##Could be better?
        ##TODO: set roi span from graph
        ##TODO: show roi on spectrum graph even if it was set or modified in control frame
        ##TODO: don't excecute this code when not connected to CS
        if self.magnitude_spectrum_graph is None:
            return
        if event.inaxes == self.magnitude_spectrum_graph.plot:
            roi_span = pysagax.si_to_float(control_frame_ref.roi_span_string.get())
            roi_freq = self.magnitude_spectrum_graph.coord_to_freq(event.xdata)
            roi_threshold = event.ydata

            self.client.update_roi_settings(
                roi_freq, roi_span, math.floor(roi_threshold)
            )

            self.magnitude_spectrum_graph.roi_center = event.xdata
            self.magnitude_spectrum_graph.roi_width = int(
                roi_span * (self.params.bin_count / self.params.iq_rate)
            )
            self.magnitude_spectrum_graph.roi_threshold = int(math.floor(event.ydata))

            control_frame_ref.roi_center_string.set(f"{roi_freq:.0f}")
            control_frame_ref.roi_threshold_string.set(f"{roi_threshold:.0f}")
            control_frame_ref.roi_span_string.set(f"{roi_span:.0f}")

    def update_sensors_and_graphs(self) -> None:
        ##TODO
        """dfg_map_server.update_timestamp()
                dfg_map_server.update_angle(df_corrected, 1e6)
            else:
                self.compass_df_graph.add_point(None)

        if (
            compass is not None
            and compass.parser.lat is not None
            and compass.parser.lon is not None
        ):
            dfg_map_server.update_lat_lon(compass.parser.lat, compass.parser.lon)"""

        assert self.df_graph is not None  ##TODO: assert for all or no compass graphs?

        ##TODO: graph df_value_std (and latest df_value??)
        self.df_graph.add_point(self.master.aggregated_roi_results["df_value_mean"], self.master.aggregated_roi_results["df_value_std"])
        self.compass_graph.add_point(self.master.compass_heading)
        self.encoder_graph.add_point(self.master.encoder_heading)

        df_corrected = calculate_df_corrected(
            df_value=self.master.aggregated_roi_results["df_value_mean"],
            compass_heading=self.master.compass_heading,
            encoder_heading=self.master.encoder_heading,
        )

        self.compass_df_graph.add_point(df_corrected)

    def plot_spectrum_packet(self, packet: CoreServiceSpectrumPacket, signal_db: float= 0., noise_db: float= 0.) -> None:
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
        self.magnitude_spectrum_graph.signal_lvl = signal_db
        self.magnitude_spectrum_graph.noise_lvl = noise_db


class StatusQueryThread(threading.Thread):
    def source_length_handler(self, cmd: str, resp: list[str]) -> None:
        if resp[0] == "0":
            source_length = int(resp[1])
            self.pb_tab.position_slider.configure(to=source_length)

    def source_position_handler(self, cmd: str, resp: list[str]) -> None:
        if resp[0] == "0":
            self.pb_tab.position_variable.set(int(resp[1]))

    def source_status_handler(self, cmd: str, resp: list[str]) -> None:
        self.pb_tab.source_configured = True if int(resp[1]) else False
        self.pb_tab.source_running = True if int(resp[2]) else False
        self.pb_tab.set_buttons_enabled()

    def recording_status_handler(self, cmd: str, resp: list[str]) -> None:
        rec_activated = True if int(resp[1]) else False
        rec_running = True if int(resp[2]) else False
        self.pb_tab.rec_status_string.set(
            "🟣"
            if (not rec_activated) and (not rec_running)
            else "🟢"
            if rec_activated and (not rec_running)
            else "🟠"
            if rec_activated and rec_running
            else "❓"
        )
        self.pb_tab.rec_status_label.configure(
            fg=(
                "Aqua"
                if (not rec_activated) and (not rec_running)
                else "LimeGreen"
                if rec_activated and (not rec_running)
                else "Red"
                if rec_activated and rec_running
                else "Red"
            )
        )

    def __init__(self, comm: CommandsHandlerThread, pb_tab: PlaybackTab) -> None:
        super().__init__(daemon=True)
        self.comm = comm
        self.pb_tab = pb_tab
        self.comm.set_response_handler("SOURCE:Status?", self.source_status_handler)
        self.comm.set_response_handler(
            "RECORDING:Status?", self.recording_status_handler
        )
        self.comm.set_response_handler("SOURCE:Length?", self.source_length_handler)
        self.comm.set_response_handler("SOURCE:Position?", self.source_position_handler)

    def run(self) -> None:
        while self.comm.is_alive():
            if not self.pb_tab.working:
                self.comm.enqueue_commands(
                    "SOURCE:Status?;RECORDING:Status?;SOURCE:Length?;SOURCE:Position?;"
                )
            time.sleep(0.2)


class PlaybackTab(ttk.Frame):
    def set_buttons_enabled(self) -> None:
        self.start_button.configure(
            state=en_if(
                self.connected
                and (not self.working)
                and self.source_configured
                and (not self.source_running)
            )
        )
        self.rec_button.configure(
            state=en_if(
                self.connected and (not self.working) and self.source_configured
            )
        )
        self.stop_button.configure(
            state=en_if(self.connected and (not self.working) and self.source_running)
        )
        self.abort_button.configure(state=en_if(self.connected and self.working))

    def __init__(self, master: tkinter.Misc, client: Client) -> None:
        super().__init__(master)
        self.position_variable = tkinter.DoubleVar()
        self.status_string = tkinter.StringVar(value="Idle")
        self.rec_status_string = tkinter.StringVar(value="🟣️")

        self.client = client
        self.connected: bool = False
        self.working: bool = False
        self.source_configured: bool = False
        self.source_running: bool = False

        self.position_slider = tkinter.Scale(
            self,
            from_=0,
            to=1,
            variable=self.position_variable,
            orient=tkinter.HORIZONTAL,
            command=self.position_commands,
        )
        self.position_slider.pack(side=tkinter.TOP, expand=True, fill=tkinter.X)
        self.start_button = tkinter.Button(self, text="▶️", command=self.start_commands)
        self.start_button.pack(side=tkinter.LEFT)
        self.rec_button = tkinter.Button(self, text="⏺️️", command=self.rec_commands)
        self.rec_button.pack(side=tkinter.LEFT)
        self.rec_status_label = tkinter.Label(
            self,
            textvariable=self.rec_status_string,
            font=tkinter.font.Font(size=16),
            fg="#ccc",
        )
        self.rec_status_label.pack(side=tkinter.LEFT, expand=False)
        self.stop_button = tkinter.Button(self, text="⏹️", command=self.stop_commands)
        self.stop_button.pack(side=tkinter.LEFT)
        self.status_label = tkinter.Label(
            self,
            textvariable=self.status_string,
            font=tkinter.font.Font(size=8),
        )
        self.status_label.pack(side=tkinter.LEFT)
        self.abort_button = tkinter.Button(self, text="⛔", command=self.abort_commands)
        self.abort_button.pack(side=tkinter.RIGHT)

        self.start_button.configure(state="disabled")
        self.rec_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.abort_button.configure(state="disabled")

    def command_status_callback(self, working: bool, current_cmd: str) -> None:
        if (
            "Status?" in current_cmd
            or "Position?" in current_cmd
            or "Length?" in current_cmd
        ):
            self.working = False
        else:
            self.working = working
        self.set_buttons_enabled()
        self.status_string.set(current_cmd)

    def position_commands(self, event: typing.Any) -> None:
        self.client.command_thread.enqueue_commands(
            f"SOURCE:Position! {self.position_variable.get()}"
        )

    def start_commands(self) -> None:
        self.client.command_thread.enqueue_commands("SOURCE:Start!")

    def rec_commands(self) -> None:
        if self.client.recording_started:
            self.client.stop_recording()
            self.rec_button.config(relief="raised")
        else:
            self.client.start_recording()
            self.rec_button.config(relief="sunken")

    def stop_commands(self) -> None:
        self.client.command_thread.enqueue_commands("SOURCE:Stop!")

    def abort_commands(self) -> None:
        self.client.command_thread.abort_commands()


class ClientWindow(tkinter.Frame):
    def __init__(self, client, root):
        self.do_stop = False

        # aggregated and current roi results, coming from StreaAndCompassProcess
        self.aggregated_roi_results = {
            "df_value_mean": None,
            "df_value_std": None,
            "df_elevation_mean": None,
            "df_elevation_std": None,
        }
        self.latest_roi_resutls = {"df_value": None, "df_elevation": None}
        self.compass_angle = None
        self.compass_heading = None  # compass angle corrected with offset
        self.encoder_angle = None
        self.encoder_heading = None  # encoder angle corrected with offset

        tkinter.Frame.__init__(self, root)
        self.pack(side="top", fill=tkinter.BOTH, expand=True)

        self.client = client  # The GUI communicates with other components of the client through this reference

        self.status_frame = StatusFrame(self, relief=tkinter.RAISED, borderwidth=1)
        self.status_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        self.connect_frame = ConnectFrame(self, relief=tkinter.RAISED, borderwidth=1)
        self.connect_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        self.plot_frame = PlotFrame(self)
        self.plot_frame.root = root
        self.plot_frame.create_canvas()
        self.plot_frame.pack(
            fill=tkinter.BOTH, expand=True, side=tkinter.TOP
        )  ##TODO: this was after bottom_frame.pack(). Should it be there?

        self.bottom_frame = tkinter.Frame(
            self, relief=tkinter.RAISED, borderwidth=1
        )  ##TODO: frames inside this will be one level deeper than connect and status frames. is it OK??
        self.bottom_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        self.control_frame = ControlFrame(
            self.bottom_frame, relief=tkinter.RAISED, borderwidth=1
        )
        self.control_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.LEFT)

        self.center_notebook = ttk.Notebook(self.bottom_frame)
        self.playback_tab = PlaybackTab(self.center_notebook, client)
        self.tab1 = ttk.Frame(self.center_notebook)
        self.stream_packets_tab = ttk.Frame(self.center_notebook)
        self.center_notebook.add(self.playback_tab, text="Playback")
        self.center_notebook.add(self.tab1, text="Status info")
        self.center_notebook.add(self.stream_packets_tab, text="Stream packets")
        self.center_notebook.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True
        )

        center_box_width = conf["display"]["center_box_width"] if conf else 60
        self.status_info_lb = tkinter.Listbox(
            self.tab1, height=4, width=center_box_width
        )
        status_info_lb_sb = tkinter.Scrollbar(self.tab1, orient="horizontal")
        status_info_lb_sb.config(command=self.status_info_lb.xview)
        status_info_lb_sb.pack(side="bottom", fill=tkinter.X)
        self.status_info_lb.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True
        )

        self.stream_packets_lb = tkinter.Listbox(
            self.stream_packets_tab, height=4, width=center_box_width
        )
        stream_packets_lb_sb = tkinter.Scrollbar(
            self.stream_packets_tab, orient="horizontal"
        )
        stream_packets_lb_sb.config(command=self.stream_packets_lb.xview)
        stream_packets_lb_sb.pack(side="bottom", fill=tkinter.X)
        self.stream_packets_lb.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True
        )

        self.stat_frame = StatFrame(
            self.bottom_frame, relief=tkinter.RAISED, borderwidth=1, width=600
        )
        self.stat_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.RIGHT)

        self.packet_handler_thread = threading.Thread(
            target=self.gui_packet_handler, daemon=True
        )
        self.packet_handler_thread.start()

    def gui_packet_handler(self):
        while not self.do_stop:
            try:
                data = self.client.stream_to_gui_queue.get(timeout=0.2)

                packet = data["cs_packet"]
                self.aggregated_roi_results = data["aggregated_roi_results"]
                self.compass_angle = data["compass_angle"]
                self.compass_heading = data["compass_heading"]
                self.encoder_angle = data["encoder_angle"]
                self.encoder_heading = data["encoder_heading"]

                try:
                    ts = datetime.fromtimestamp(packet.time_ns / 1e9, tz=None)
                    packet_string = (
                        f"[{packet.stream_id}] {ts.strftime('%H:%M:%S')}.{int((packet.time_ns % 1e9) / 1e6):03d} - "
                        f"{str(packet)} - c_angle={self.compass_angle}; e_angle={self.encoder_angle}"
                    )
                    self.stream_packets_lb.insert(tkinter.END, packet_string)
                    self.stream_packets_lb.delete(
                        0, self.stream_packets_lb.size() - 1000
                    )
                    self.stream_packets_lb.see(tkinter.END)

                    if isinstance(packet, CoreServiceSpectrumPacket):
                        signal_db, noise_db = self.calculate_snr(packet)
                        self.stat_frame.snr_string.set(f"{signal_db-noise_db:.1f}dB")
                        self.plot_frame.plot_spectrum_packet(packet, signal_db, noise_db)

                    if isinstance(
                        packet, CoreServiceDebugPacket
                    ):  # updating peak plots
                        if packet.title == "peaks":
                            regex = r"peak(\d+)=(\d+)"
                            matches = re.findall(
                                regex, str(packet)
                            )  # creating a list of (ChannelID, PeakValue) tuples from the debug message
                            peaks = [peak[1] for peak in matches]
                            self.stat_frame.update_peak_plot(peaks)
                        elif packet.title == "q":
                            quality = float(packet.contents.decode().strip())
                            self.stat_frame.quality_value_string.set(f"{quality:.2f}")

                    if isinstance(packet, CoreServiceROIResultPacket):
                        self.latest_roi_resutls["df_value"] = packet.roi_azimuth
                        self.latest_roi_resutls["df_elevation"] = packet.roi_elevation

                        self.stat_frame.update_stats(
                            self.latest_roi_resutls, self.aggregated_roi_results
                        )

                    if isinstance(packet, CoreServiceEOFPacket):
                        self.info_update_handler(
                            "End of file reached for Sigmf recording",
                            source="GUI packet handler",
                        )
                except Exception as e:
                    if not self.do_stop:
                        print("[GUI packet handler]", e)
                        traceback.print_tb(e.__traceback__)
            except queue.Empty:
                pass
            except Exception as e:
                print("[GUI packet handler]", e)
                traceback.print_tb(e.__traceback__)
                return

    def command_status_msg_handler(self, message: str):
        if message.startswith("#info"):
            message = message[len("#info") :]
        elif message.startswith("#action"):
            message = message[len("#action") :]
            if message == "send_commands_finished":
                # self.decrease_unfinished_send_commands()
                return
        else:  # status updates have no prefix, these should also be shown on status_frame
            self.set_command_status(message)
        self.info_update_handler(message, "Command Thread")

    def stream_status_msg_handler(self, message: str):
        if message.startswith("#encoder"):
            message = message[len("#encoder") :]
            self.info_update_handler(message, source="Encoder")
        elif message.startswith("#compass"):
            message = message[len("#compass") :]
            self.info_update_handler(message, source="Compass")
        else:  # status updates have no prefix, these should also be shown on status_frame
            self.set_stream_status(message)
            self.info_update_handler(message, source="Stream Process")
        # TODO: update compass end map server in status_frame

    def recording_status_msg_handler(self, message: str):
        # if message.startswith("#info"):
        #     message = message[len("#info") :]
        # elif message.startswith("#action"):
        #     message = message[len("#action") :]
        #     if message == "send_commands_finished":
        #         self.decrease_unfinished_send_commands()
        #         return
        self.info_update_handler(message, "Recording Thread")
        
    def map_server_status_msg_handler(self, message: str):
        if message.startswith("#info"):
            message = message[len("#info") :]
            self.status_frame.status_map_server_string.set(message)
            return
        self.info_update_handler(message, "Map Server")

    def set_stream_status(self, message: str) -> None:
        try:
            self.status_frame.status_stream_string.set(message)
        except:
            pass  ##TODO: when exiting, this gets called after the window no longer exists

    def set_command_status(self, message: str) -> None:
        try:
            self.status_frame.status_command_string.set(message)
        except:
            pass  ##TODO: when exiting, this gets called after the window no longer exists

    def connect_commands(self):
        connect_action = self.connect_action
        disconnect_action = self.disconnect_action
        host_address = self.connect_frame.host_address.get()
        encoder_port = self.connect_frame.encoder_port_string.get()
        self.client.connect_commands(
            connect_action, disconnect_action, host_address, encoder_port
        )

    def disconnect_commands(self):
        self.client.disconnect_commands()

    def connect_action(self) -> None:
        """
        Events triggered by successful connection
        """
        self.connect_frame.connect_button.configure(state="disabled")
        self.connect_frame.host_entry.configure(state="disabled")
        self.connect_frame.disconnect_button.configure(state="normal")
        self.connect_frame.channel_spectrum_combo.configure(state="normal")

        self.control_frame.configure_button.configure(state="normal")

        self.playback_tab.connected = True
        self.playback_tab.set_buttons_enabled()
        # self.control_frame.rec_button.configure(state="normal")

        try:  ##TODO: move this from GUI thread
            path_list = b""
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(
                    (self.connect_frame.host_address.get(), 12939)
                )  ##TODO port no. to args
                s.sendall(b"nc")
                while True:
                    data = s.recv(1024)
                    if not data:
                        break
                    path_list += data
            path_list = path_list.decode().split()
            path_list = sorted([path.strip() for path in path_list])
            self.control_frame.source_file_path_combo["values"] = path_list
        except Exception as e:
            print("[Updating recording paths]", e)
        if self.plot_frame.animation is not None:
            try:
                self.plot_frame.animation.event_source.start()
            except Exception as e:
                pass

    def disconnect_action(self) -> None:
        """
        Events triggered by client disconnect
        """
        try:
            self.connect_frame.disconnect_button.configure(state="disabled")
            self.connect_frame.host_entry.configure(state="normal")
            self.connect_frame.connect_button.configure(state="normal")
            self.connect_frame.channel_spectrum_combo.configure(state="disabled")

            self.control_frame.configure_button.configure(state="disabled")

            self.playback_tab.connected = False
            self.playback_tab.set_buttons_enabled()
            self.disconnect_commands()  # to disconnect the other thread
        except:
            pass  # it might happen when closing the window
        try:
            self.plot_frame.animation.event_source.stop()
        except Exception as e:
            pass

    def info_update_handler(self, update_string: str | list[str], source: str = None):
        if self.do_stop:  # this might happen when closing the window
            return
        if not isinstance(update_string, list):
            update_string = [update_string]
        for line in update_string:
            if source is not None:
                line = f"[{source}]: {line}"
            self.status_info_lb.insert(tkinter.END, line)
            self.status_info_lb.delete(0, self.stream_packets_lb.size() - 1000)
            self.status_info_lb.see(tkinter.END)
            print(datetime.now().strftime("%m.%d. %H:%M:%S"), line)

    def calculate_snr(self, packet: CoreServiceSpectrumPacket) -> (float, float):
        min_freq = packet.center_frequency - packet.iq_rate / 2
        max_freq = packet.center_frequency + packet.iq_rate / 2
        bin_freqs = np.linspace(min_freq, max_freq, packet.bin_count)

        spectrum = list(zip(bin_freqs, packet.magnitude_spectrum))
        
        roi_center = pysagax.si_to_float(self.control_frame.roi_center_string.get()) 
        roi_span = pysagax.si_to_float(self.control_frame.roi_span_string.get())
        roi_min = roi_center - roi_span / 2
        roi_max = roi_center + roi_span / 2

        signal_bins = [a for f, a in spectrum if roi_min<f and f<roi_max]
        noise_bins = [a for f, a in spectrum if not(roi_min<f and f<roi_max)]

        if len(signal_bins) == 0 or len(noise_bins) == 0:
            return 0,0
        
        signal_db = max(signal_bins)
        noise_db = sum(noise_bins) / len(noise_bins)

        return signal_db, noise_db

class RecordingThread(threading.Thread):
    def __init__(
        self, cs_packet_queue: queue.Queue, status_queue: queue.Queue[str]
    ) -> None:
        super().__init__(daemon=True)
        self.cs_packet_queue = cs_packet_queue
        self.status_queue = status_queue

        self.do_stop = False

        self.latest_peaks = [0, 0, 0, 0]
        self.latest_quality = 0

        self.buffer = {
            "time_ns": [],
            "df_angle": [],
            "df_corrected": [],
            "compass_angle": [],
            "compass_heading": [],
            "encoder_angle": [],
            "encoder_heading": [],
            "df_elevation": [],
            "quality": [],
            "peak0": [],
            "peak1": [],
            "peak2": [],
            "peak3": [],
            "df_angle_mean": [],
            "df_angle_std": [],
            "df_elevation_mean": [],
            "df_elevation_std": [],
            "lat": [],
            "lon": [],
        }

    def run(self) -> None:
        self.status_queue.put("Recording started")
        start_time_string = datetime.now().strftime("%Y%m%d_%H%M%S")
        while not self.do_stop:
            try:
                data = self.cs_packet_queue.get(timeout=0.2)
                self.handle_packet(data=data)
            except queue.Empty:
                pass
            except Exception as e:
                print("[Recording thread]", e)
                traceback.print_tb(e.__traceback__)
                return
        self.status_queue.put("saving recording...")
        try:
            self.save_recording(start_time_string)
        except Exception as e:
            self.status_queue.put(f"Error while saving recording: {e}")

    def handle_packet(self, data) -> None:
        ##TODO: many similarities with client window packet handler. Maybe export those to a single function?
        packet = data["cs_packet"]
        try:
            time_ns = packet.time_ns
            if isinstance(packet, CoreServiceDebugPacket):
                # save the peaks to later match with the next ROI results
                if packet.title == "peaks":
                    regex = r"peak(\d+)=(\d+)"
                    matches = re.findall(
                        regex, str(packet)
                    )  # creating a list of (ChannelID, PeakValue) tuples from the debug message
                    peaks = [peak[1] for peak in matches]
                    self.latest_peaks = peaks
                elif packet.title == "q":
                    quality = float(packet.contents.decode().strip())
                    self.latest_quality = quality

            if isinstance(packet, CoreServiceROIResultPacket):
                compass_angle = data["compass_angle"]
                compass_heading = data["compass_heading"]
                encoder_angle = data["encoder_angle"]
                encoder_heading = data["encoder_heading"]

                df_angle = packet.roi_azimuth
                df_elevation = packet.roi_elevation
                df_corrected = calculate_df_corrected(
                    df_value=df_angle,
                    compass_heading=compass_heading,
                    encoder_heading=encoder_heading,
                )

                self.buffer["time_ns"].append(time_ns)
                self.buffer["df_angle"].append(df_angle)
                self.buffer["df_corrected"].append(df_corrected)
                self.buffer["compass_angle"].append(compass_angle)
                self.buffer["compass_heading"].append(compass_heading)
                self.buffer["encoder_angle"].append(encoder_angle)
                self.buffer["encoder_heading"].append(encoder_heading)
                self.buffer["df_elevation"].append(df_elevation)
                self.buffer["quality"].append(self.latest_quality)
                self.buffer["peak0"].append(self.latest_peaks[0])
                self.buffer["peak1"].append(self.latest_peaks[1])
                self.buffer["peak2"].append(self.latest_peaks[2])
                self.buffer["peak3"].append(self.latest_peaks[3])
                self.buffer["df_angle_mean"].append(
                    data["aggregated_roi_results"]["df_value_mean"]
                )
                self.buffer["df_angle_std"].append(
                    data["aggregated_roi_results"]["df_value_std"]
                )
                self.buffer["df_elevation_mean"].append(
                    data["aggregated_roi_results"]["df_elevation_mean"]
                )
                self.buffer["df_elevation_std"].append(
                    data["aggregated_roi_results"]["df_elevation_std"]
                )
                self.buffer["lat"].append(data["gps_lat"])
                self.buffer["lon"].append(data["gps_lon"])

        except Exception as e:
            print("[Recording packet handler]", e)
            traceback.print_tb(e.__traceback__)

    def save_recording(self, start_time_string):
        dataframe = pd.DataFrame(data=self.buffer)

        os.makedirs("racclient_recordings", exist_ok=True)
        filepath = f"racclient_recordings/{start_time_string}.csv"
        dataframe.to_csv(filepath)
        self.status_queue.put(f"{len(dataframe.index)} lines saved at {filepath}")

        ##TODO: plot results of recording
        """ df_value_recording_deg = [d * 180 / np.pi if d is not None else None for d in self.buffer["df_angle"]]
        df_corrected_recording_deg = [d * 180 / np.pi if d is not None else None for d in self.buffer["df_corrected"]]
        compass_heading_recording_deg = [d * 180 / np.pi if d is not None else None for d in self.buffer["compass_heading"]]
        encoder_heading_recording_deg = [d * 180 / np.pi if d is not None else None for d in self.buffer["encoder_heading"]]
        fig, (ax1, ax2) = pyplot.subplots(1, 2)
        ax1.plot(compass_heading_recording_deg, df_value_recording_deg, color="red", label="compass-DF")
        ax1.plot(encoder_heading_recording_deg, df_value_recording_deg, color="green", label="encoder-DF")
        ax1.legend()
        
        ax2.plot(df_value_recording_deg, color="blue", label="DF angle")
        ax2.plot(df_corrected_recording_deg, color="cyan", label="DF corrected")
        ax2.plot(compass_heading_recording_deg, color="red", label="compass")
        ax2.plot(encoder_heading_recording_deg, color="green", label="encoder")
        ax2.legend()
        
        ax1.grid(visible=True)
        ax1.set_ylabel("DF angle")
        ax1.set_xlabel("Compass and encoder angle")
        ax2.grid(visible=True)
        ax2.set_ylabel("Angle")
        ax2.set_xlabel("Sample")
        ax1.set_xlim(-180, 180)
        ax1.set_ylim(-180, 180)
        ax2.set_ylim(-180, 180)
        pyplot.show(block=False) """


class CommandsConnectionThread(BaseConnection, threading.Thread):
    def __init__(self, status_queue: queue.Queue[str]) -> None:
        BaseConnection.__init__(self)
        threading.Thread.__init__(self, daemon=True)
        self.incoming_buffer: bytearray = bytearray()
        self.status_text: str = ""
        self.incoming_messages_queue: queue.Queue[str] = queue.Queue()

        self.status_queue = status_queue

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
        self.status_queue.put(message)

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.disconnect = False
        self.run_socket()

    def send_command(self, cmd: str) -> Optional[str]:
        self.send_on_socket(cmd.encode())
        try:
            return self.incoming_messages_queue.get(block=True, timeout=30)
        except queue.Empty:
            return None


class CommandsHandlerThread(threading.Thread):
    def __init__(
        self,
        conn: CommandsConnectionThread,
        status_callback: Callable[[bool, str], None],
        status_queue: queue.Queue[str],
    ):
        super().__init__(daemon=True)
        self.conn = conn
        self.command_queue: queue.Queue[str] = queue.Queue()
        self.do_abort: bool = False
        self.status_callback = status_callback
        """
        Callback to display status of commands
        bool: is working on a command
        str: the command it is working on
        """
        self.status_queue = status_queue
        self.response_handlers: dict[str, Callable[[str, list[str]], None]] = {}

    def set_response_handler(
        self, command: str, handler: Callable[[str, list[str]], None]
    ):
        self.response_handlers[command] = handler

    def run(self) -> None:
        while not self.conn.connected:
            sleep(0.1)
            if self.conn.disconnect:
                return
        while self.conn.connected:
            if not self.command_queue.empty():
                while (
                    (not self.command_queue.empty())
                    and not self.do_abort
                    and self.conn.connected
                ):
                    command = self.command_queue.get(block=True, timeout=1)
                    self.status_callback(True, command)
                    response = self.conn.send_command(command)
                    if response is None:
                        self.timeout_handler(command)
                    else:
                        self.response_handler(command, response)
                self.status_queue.put("#action" + "send_commands_finished")
                self.status_callback(False, "")
            sleep(0.1)

    def timeout_handler(self, command: str) -> None:
        self.status_queue.put(f"Command {command} timed out.")

    def response_handler(self, command: str, response: str) -> None:
        response_parts = response.split(" ")
        error_code = int(response_parts[0])
        for key, handler in self.response_handlers.items():
            if key in command:
                handler(command, response_parts)
        if error_code:
            self.status_queue.put(f'#infoError with command "{command}": {response}')

    def enqueue_commands(self, commands: str):
        self.do_abort = False
        cmd = commands.replace("\n", "").replace("\r", "")
        for cmd_line in cmd.split(";"):  # One command per line
            if not cmd_line:
                continue
            cmd_line = cmd_line.strip()
            cmd_line += ";"
            self.command_queue.put(cmd_line)

    def abort_commands(self):
        self.do_abort = True
        while not self.command_queue.empty():
            self.command_queue.get()  # clear queue
        self.status_callback(False, "")


class MapServer(DFGMapServer):
    def __init__(self, cs_packet_queue: queue.Queue, status_queue: queue.Queue[str]) -> None:
        super().__init__()
        self.cs_packet_queue = cs_packet_queue
        self.status_queue = status_queue
        threading.Thread(target= self.cs_packet_handler, daemon=True).start()

    def cs_packet_handler(self) -> None:
        while self.run_thread:
            self.read_queue()
    
    def read_queue(self):
        data = None
        try:
            while True:
                data = self.cs_packet_queue.get_nowait()
        except queue.Empty:
            pass
        except Exception as e:
            print("[MapServer thread]", e)
            traceback.print_tb(e.__traceback__)
            return
        if data is not None:            
            self.handle_packet(data=data)
        sleep(0.2) #send updates to clients every 0.2 seconds
        self.status_queue.put(f"#info" + "Up on port {self.port}, "
                                f"{self.count_clients()} clients, "
                                f"{self.total_packets} packets")

    def handle_packet(self, data):
        df_value_mean = data["aggregated_roi_results"]["df_value_mean"]
        if not df_value_mean:
            return
        compass_heading = data["compass_heading"]
        encoder_heading = data["encoder_heading"]
        
        df_corrected = calculate_df_corrected(
            df_value=df_value_mean,
            compass_heading=compass_heading,
            encoder_heading=encoder_heading,
        )
        lat = data["gps_lat"]
        lon = data["gps_lon"]

        isvalid = lambda nums: all([not math.isnan(x) if x is not None else False for x in nums])
        if not isvalid([df_corrected, lat, lon]):
            return #only update the map server if all values are valid
        
        self.update_timestamp()
        self.update_angle(df_corrected, 1e6) #TODO: add frequency
        self.update_lat_lon(lat, lon)
        self.update_clients()
        print(f"{lat}, {lon}, {df_corrected}")

# Owner class for the client
class Client:
    def __init__(self, root):
        self.manager = multiprocessing.get_context("spawn").Manager()

        self.stream_to_gui_queue = self.manager.Queue(maxsize=100)
        self.stream_to_rec_queue = None
        self.stream_to_map_queue = self.manager.Queue(maxsize=10)

        self.stream_process_multiqueue = MultiQueue([self.stream_to_gui_queue])

        self.client_window = ClientWindow(self, root)
        self.command_connection_thread: Optional[CommandsConnectionThread] = None
        self.command_thread: Optional[CommandsHandlerThread] = None
        self.status_query_thread: Optional[StatusQueryThread] = None
        self.stream_process = None
        self.recording_thread = None
        self.dfg_map_server = None
        self.encoder_thread = None

        self.stream_process_watcher_queue: multiprocessing.Queue[
            str
        ] = multiprocessing.Queue()
        self.command_thread_watcher_queue: multiprocessing.Queue[
            str
        ] = multiprocessing.Queue()
        self.recording_thread_watcher_queue: multiprocessing.Queue[
            str
        ] = multiprocessing.Queue()
        self.map_server_thread_watcher_queue: multiprocessing.Queue[
            str
        ] = multiprocessing.Queue()

        self.disconnect_value = self.manager.Value("i", 0)
        """
        Setting the '1' value of the disconnect_value multiprocessing variable will end the multiprocessing task on the
        next iteration.
        """

        self.mean_window_width_value = self.manager.Value(
            "float", conf["stats"]["mean_window_width_seconds"] if conf else 0
        )

        self.recording_started = False

        self.do_stop = False
        self.watcher_thread = threading.Thread(target=self.watcher_thread)
        self.watcher_thread.start()

    def watcher_thread(self):
        while not self.do_stop:
            try:
                do_sleep = True  # if every queue is empty -> sleep
                if self.stream_process is not None:
                    try:
                        msg = self.stream_process_watcher_queue.get_nowait()
                        self.client_window.stream_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass

                if self.command_thread is not None:
                    try:
                        msg = self.command_thread_watcher_queue.get_nowait()
                        self.client_window.command_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass

                if self.recording_thread is not None:
                    try:
                        msg = self.recording_thread_watcher_queue.get_nowait()
                        self.client_window.recording_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass
                if self.dfg_map_server is not None:
                    try:
                        msg = self.map_server_thread_watcher_queue.get_nowait()
                        self.client_window.map_server_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass
                ##TODO: msg_handler functions might not need separate threads
                if do_sleep:
                    sleep(0.1)
            except Exception as e:
                if not self.do_stop:
                    raise e
        ##TODO: empty and join watcher queues before terminating thread

    def send_commands(self, cmd: str) -> None:
        """
        Send the command from the command entry box to the client. Called on pressing the Return key in the autocomplete box.
        """
        assert self.command_thread is not None
        if (
            self.command_connection_thread is None
        ):  ##TODO: After disconnecting command_thread should be None
            return
        self.command_thread.enqueue_commands(cmd)

    def command_status_callback(self, working: bool, current_cmd: str):
        self.command_thread_watcher_queue.put("#action" + "send_commands_finished")
        self.client_window.playback_tab.command_status_callback(working, current_cmd)

    def connect_commands(
        self, connect_action, disconnect_action, host_address, encoder_port: str = ""
    ) -> None:
        """
        Action of the "Connect" button
        """
        self.command_connection_thread = CommandsConnectionThread(
            self.command_thread_watcher_queue
        )
        self.command_connection_thread.connect_action = connect_action
        self.command_connection_thread.disconnect_action = disconnect_action
        self.command_connection_thread.host_port = f"{host_address}:12936"
        self.command_connection_thread.start()

        self.command_thread = CommandsHandlerThread(
            conn=self.command_connection_thread,
            status_callback=self.command_status_callback,
            status_queue=self.command_thread_watcher_queue,
        )

        self.command_thread.start()
        self.command_thread.set_response_handler(
            "CORE:Version?",
            lambda cmd, resp: self.command_thread_watcher_queue.put(
                f"#infoCS Version {resp[1]}.{resp[2]}.{resp[3]}"
                f"-{resp[4]}+{resp[5]} VCS:{resp[6]}"
            ),
        )
        self.command_thread.set_response_handler(
            "SOURCE:Configure!",
            lambda cmd, resp: self.command_thread_watcher_queue.put(
                "#infoCore Service configured"
                if int(resp[0]) == 0
                else "#infoCore Service conf failed"
            ),
        )
        self.command_thread.set_response_handler(
            "ROI:Configure!",
            lambda cmd, resp: self.command_thread_watcher_queue.put(
                "#infoCore Service ROI configured"
                if int(resp[0]) == 0
                else "#infoCore Service ROI failed"
            ),
        )
        self.command_thread.set_response_handler(
            "RECORDING:Stop!",
            lambda cmd, resp: self.command_thread_watcher_queue.put(
                f"#infoCS Recordings done: {', '.join(resp)}"
            ),
        )
        self.status_query_thread = StatusQueryThread(
            self.command_thread, self.client_window.playback_tab
        )
        self.status_query_thread.start()

        self.disconnect_value.value = False
        self.stream_process = StreamAndCompassProcess(
            self.stream_process_multiqueue,
            self.disconnect_value,
            self.stream_process_watcher_queue,
        )

        self.stream_process.host_port = f"{host_address}:12937"
        self.stream_process.compass_host_port = f"{host_address}:12938"
        self.stream_process.encoder_port = encoder_port
        self.stream_process.mean_window_seconds = self.mean_window_width_value
        self.stream_process.use_sensor_fusion = conf["compass"]["use_sensor_fusion"] if conf else False
        self.stream_process.start()

        self.dfg_map_server = MapServer(self.stream_to_map_queue, self.map_server_thread_watcher_queue)
        self.stream_process_multiqueue.add_queue(self.stream_to_map_queue)
        self.dfg_map_server.host = conf["map_server"]["host"] if conf else '0.0.0.0'
        self.dfg_map_server.port = conf["map_server"]["port"] if conf else 20000
        self.dfg_map_server.start()

    def do_configuration(
        self,
        freq,
        bw,
        gain,
        bin_count,
        burst_stride,
        roi_center,
        roi_span,
        roi_threshold,
        from_file,
        source_file_path,
    ) -> None:
        connect_string = "UHD"

        if from_file:
            if source_file_path[-1] != "/":
                source_file_path = source_file_path + "/"
            self.send_commands(
                f"CORE:Version?;"
                f'SOURCE:Path! SigMF "{source_file_path}recording.sigmf-collection";'
                f"SOURCE:Position! 0;"
                f"AOA:BinCount! {bin_count};"
                f"SOURCE:BurstStride! {burst_stride};"
                f"SOURCE:Configure!;"
                f"AOA:Configure!;"
                f"ROI:Enable! 1;"
                f"ROI:CenterFrequency! {roi_center:.0f};"
                f"ROI:Span! {roi_span:.0f};"
                f"ROI:Threshold! {roi_threshold};"
                f"ROI:Configure!;"
            )
        else:
            self.send_commands(
                f"CORE:Version?;"
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
                f"ROI:Enable! 1;"
                f"ROI:CenterFrequency! {roi_center:.0f};"
                f"ROI:Span! {roi_span:.0f};"
                f"ROI:Threshold! {roi_threshold};"
                f"ROI:Configure!;"
            )

    def disconnect_commands(self) -> None:
        """
        Action of the "Disconnect" button
        """
        if self.command_connection_thread is not None:
            self.command_connection_thread.disconnect = True

        if self.stream_process is not None:
            if self.disconnect_value is not None:
                self.disconnect_value.value = True
        ###TODO
        """
        if self.encoder_thread is not None:
            self.encoder_thread.close()
        global compass
        if compass is not None:
            compass.do_stop = True
            compass = None
        global dfg_map_server
        dfg_map_server.run_thread = False
        dfg_map_server.join() """

        # TODO: properly make these threads stop after disconnect
        """ self.command_thread.join()
        self.stream_thread.join() """

    def update_roi_settings(self, roi_center, roi_span, roi_threshold):
        self.send_commands(
            f"ROI:CenterFrequency! {roi_center:.0f};"
            f"ROI:Span! {roi_span:.0f};"
            f"ROI:Threshold! {roi_threshold:.0f};"
            f"ROI:Configure!;"
        )

    def start_recording(self):
        self.start_local_recording()
        self.send_commands("RECORDING:Start!;")
        self.recording_started = True
        ##TODO: start local recording if CS is also recording when connecting to it

    def stop_recording(self):
        self.stop_local_recording()
        self.send_commands("RECORDING:Stop!;")
        self.recording_started = False

    def start_local_recording(self):
        self.stream_to_rec_queue = self.manager.Queue()  # TODO: set some large maxsize
        self.stream_process_multiqueue.add_queue(self.stream_to_rec_queue)
        self.recording_thread = RecordingThread(
            cs_packet_queue=self.stream_to_rec_queue,
            status_queue=self.recording_thread_watcher_queue,
        )
        self.recording_thread.start()

    def stop_local_recording(self):
        self.recording_thread.do_stop = True
        self.stream_process_multiqueue.remove_queue(self.stream_to_rec_queue)
        self.stream_to_rec_queue = None


def on_close():
    global root
    # dfg_map_server.run_thread = False
    ex.disconnect_commands()
    sleep(0.5)
    ex.do_stop = True
    ex.client_window.do_stop = True
    ex.client_window.quit()
    root.destroy()


def main() -> None:
    global ex
    global root
    global conf
    parser = argparse.ArgumentParser(description="RacClient")
    parser.add_argument("config", nargs="?", default="racclient.toml")
    args = parser.parse_args()
    conf = None
    if os.path.isfile(args.config):
        print("Config file found")
        with open(args.config, "rb") as f:
            conf = tomllib.load(f)
        print(f"Config file loaded: {repr(conf)}")
    else:
        print("Config file not found")
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = Client(root)
    root.geometry("1200x850")
    root.wm_title(f"Sagax Direction Finder Client Application {pysagax.__version__}")
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
