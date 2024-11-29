import math
import re
import tkinter
import tkinter.font
from tkinter import ttk
from typing import Any

import numpy as np

from pysagax.util.mat import normalize_angle

import pysagax.message.heading_pb2 as proto_heading
import pysagax.message.data_pb2 as proto_data
from google.protobuf.timestamp_pb2 import Timestamp
from scipy.spatial.transform import Rotation


class PeakChart(tkinter.Canvas):
    def __init__(self, master, *args, **kwargs):
        super().__init__(
            master,
            bg="white",
            bd=0,
            highlightthickness=2,
            highlightbackground="black",
            height=59,
            *args,
            **kwargs,
        )
        self.config(height=14)

        # colors are repeated if more channels are plotted
        self.channel_color_list = ["yellow", "dodger blue", "green", "red"]
        self.grid(
            column=0, row=5, columnspan=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        self.peak_bars = []
        self.peak_texts = []

        # 3 of the 4 coordinates needed to draw rectangles only change and need to be calculated
        # if _reconfigure_canvas is called. This 2D list stores those.
        self.peak_bar_fix_coords = []

    def _reconfigure_canvas(self, no_channels: int):
        """Reconfigure the canvas and the bar plots if the number of channels changes"""
        self.config(height=no_channels * 15 -1)  # canvas height depends on no_channels
        
        for bar, peak_text in zip(self.peak_bars, self.peak_texts):
            self.delete(bar)
            self.delete(peak_text)
        self.peak_bar_fix_coords = []
        self.peak_bars = []
        self.peak_texts = []
        
        for i in range(no_channels):
            fix_coords = [2, 2 + i * 15, 14 + i * 15]
            bar = self.create_rectangle(
                fix_coords[0],
                fix_coords[1],
                100,
                fix_coords[2],
                fill=self.channel_color_list[i % len(self.channel_color_list)],
            )
            text = self.create_text(
                30, 8 + i * 15, fill="black", font=("Helvetica 7 bold")
            )

            self.peak_bar_fix_coords.append(fix_coords)
            self.peak_bars.append(bar)
            self.peak_texts.append(text)

    def update(self, peaks: list[Any]) -> None:
        """
        Updates the bar plots for peak values.
        """
        if len(peaks) == 0:
            return
        if len(self.peak_bars) != len(peaks):
            self._reconfigure_canvas(len(peaks))
        max_width = self.winfo_width()
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
            (
                2 + (1 - peak / min_dbfs_level) * (max_width - 4)
                if peak != float("-inf")
                else 0
            )
            for peak in peaks_dbfs
        ]  # logarithmic scaling
        
        for bar, fix_coords, bar_width in zip(
            self.peak_bars, self.peak_bar_fix_coords, bar_widths
        ):
            self.coords(bar, fix_coords[0], fix_coords[1], bar_width, fix_coords[2])

        for peak_text, dbfs_value in zip(self.peak_texts, peaks_dbfs):
            new_string = re.sub(
                r"^-(0\.?0*)$", r"\1", f"{dbfs_value:.0f}"
            )  # formatting numbers rounded to -0 to +0
            self.itemconfig(peak_text, text=new_string)


class StatFrame(tkinter.Frame):
    def __init__(self, master: tkinter.Misc, *args: Any, **kwargs: Any):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.df_value_string = tkinter.StringVar(value="NaN")
        self.df_value_mean_string = tkinter.StringVar(value="NaN")
        self.df_value_deviation_string = tkinter.StringVar(value="NaN")
        # self.df_value_rms_string = tkinter.StringVar(value="NaN")
        self.df_elev_string = tkinter.StringVar(value="NaN")
        self.df_elev_mean_string = tkinter.StringVar(value="NaN")
        self.df_elev_deviation_string = tkinter.StringVar(value="NaN")

        self.quality_value_string = tkinter.StringVar(value="NaN")
        self.snr_string = tkinter.StringVar(value="NaN")
        self.frequency_string = tkinter.StringVar(value="NaN")
        self.bandwidth_string = tkinter.StringVar(value="NaN")
        self.lat_string = tkinter.StringVar(value="NaN")
        self.lon_string = tkinter.StringVar(value="NaN")
        self.altitude_string = tkinter.StringVar(value="NaN")
        self.yaw_string = tkinter.StringVar(value="NaN")
        self.pitch_string = tkinter.StringVar(value="NaN")
        self.roll_string = tkinter.StringVar(value="NaN")
        self.packet_time_string = tkinter.StringVar(value="")

        self.columnconfigure(0, weight=1, minsize=50)
        self.columnconfigure(1, weight=1, minsize=60)
        self.columnconfigure(2, weight=1, minsize=60)
        self.columnconfigure(3, weight=1, minsize=60)

        disp_font = tkinter.font.Font(family="serif", size=14)

        angle_label = ttk.Label(self, text="angle:")
        angle_label.grid(column=1, row=0, sticky=tkinter.W, padx=5, pady=5)
        mean_label = ttk.Label(self, text="mean:")
        mean_label.grid(column=2, row=0, sticky=tkinter.W, padx=5, pady=5)
        deviation_label = ttk.Label(self, text="deviation:")
        deviation_label.grid(column=3, row=0, sticky=tkinter.W, padx=5, pady=5)

        df_value_label = ttk.Label(self, text="DF angle:")
        df_value_label.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=5)
        display_kwargs = {
            "font": disp_font,
            "foreground": "red",
            "background": "yellow",
            "width": 7,
        }
        df_value_disp = ttk.Label(
            self, textvariable=self.df_value_string, **display_kwargs
        )
        df_value_disp.grid(
            column=1, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )
        df_value_mean_disp = ttk.Label(
            self, textvariable=self.df_value_mean_string, **display_kwargs
        )
        df_value_mean_disp.grid(
            column=2, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )
        df_value_deviation_disp = ttk.Label(
            self, textvariable=self.df_value_deviation_string, **display_kwargs
        )
        df_value_deviation_disp.grid(
            column=3, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        df_elev_label = ttk.Label(self, text="DF elevation:")
        df_elev_label.grid(column=0, row=2, sticky=tkinter.W, padx=5, pady=5)
        df_elev_disp = ttk.Label(
            self, textvariable=self.df_elev_string, **display_kwargs
        )
        df_elev_disp.grid(column=1, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=3)
        df_elev_mean_disp = ttk.Label(
            self, textvariable=self.df_elev_mean_string, **display_kwargs
        )
        df_elev_mean_disp.grid(
            column=2, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )
        df_elev_deviation_disp = ttk.Label(
            self, textvariable=self.df_elev_deviation_string, **display_kwargs
        )
        df_elev_deviation_disp.grid(
            column=3, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        quality_value_label = ttk.Label(self, text="Signal quality:")
        quality_value_label.grid(column=0, row=3, sticky=tkinter.W, padx=5, pady=5)
        quality_value_disp = ttk.Label(
            self, textvariable=self.quality_value_string, **display_kwargs
        )
        quality_value_disp.grid(
            column=1, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        # SNR
        snr_label = ttk.Label(self, text="SNR:")
        snr_label.grid(column=2, row=3, sticky=tkinter.W, padx=5, pady=5)
        snr_disp = ttk.Label(self, textvariable=self.snr_string, **display_kwargs)
        snr_disp.grid(column=3, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=3)

        # Frequency
        frequency_label = ttk.Label(self, text="Frequency:")
        frequency_label.grid(column=0, row=4, sticky=tkinter.W, padx=5, pady=5)
        frequency_disp = ttk.Label(
            self, textvariable=self.frequency_string, **display_kwargs
        )
        frequency_disp.grid(
            column=1, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        # Bandwidth
        bandwidth_label = ttk.Label(self, text="Bandwidth:")
        bandwidth_label.grid(column=2, row=4, sticky=tkinter.W, padx=5, pady=5)
        bandwidth_disp = ttk.Label(
            self, textvariable=self.bandwidth_string, **display_kwargs
        )
        bandwidth_disp.grid(
            column=3, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        # # HEADING DATA
        lat_lon_label = ttk.Label(self, text="Lat, Lon:")
        lat_lon_label.grid(column=0, row=6, sticky=tkinter.W, padx=5, pady=5)
        lat_disp = ttk.Label(self, textvariable=self.lat_string, **display_kwargs)
        lat_disp.grid(column=1, row=6, sticky=tkinter.E + tkinter.W, padx=5, pady=3)
        lon_disp = ttk.Label(self, textvariable=self.lon_string, **display_kwargs)
        lon_disp.grid(column=2, row=6, sticky=tkinter.E + tkinter.W, padx=5, pady=3)

        altitude_label = ttk.Label(self, text="Altitude (m):")
        altitude_label.grid(column=0, row=7, sticky=tkinter.W, padx=5, pady=5)
        altitude_disp = ttk.Label(
            self, textvariable=self.altitude_string, **display_kwargs
        )
        altitude_disp.grid(
            column=1, row=7, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        attitude_label = ttk.Label(self, text="Attitude (YPR, deg):")
        attitude_label.grid(column=0, row=8, sticky=tkinter.W, padx=5, pady=5)
        yaw_disp = ttk.Label(self, textvariable=self.yaw_string, **display_kwargs)
        yaw_disp.grid(column=1, row=8, sticky=tkinter.E + tkinter.W, padx=5, pady=3)
        pitch_disp = ttk.Label(self, textvariable=self.pitch_string, **display_kwargs)
        pitch_disp.grid(column=2, row=8, sticky=tkinter.E + tkinter.W, padx=5, pady=3)
        roll_disp = ttk.Label(self, textvariable=self.roll_string, **display_kwargs)
        roll_disp.grid(column=3, row=8, sticky=tkinter.E + tkinter.W, padx=5, pady=3)

        time_label = ttk.Label(self, text="Packet time:")
        time_label.grid(column=0, row=9, sticky=tkinter.W, padx=5, pady=5)
        time_disp = ttk.Label(
            self, textvariable=self.packet_time_string, **display_kwargs
        )
        time_disp.grid(
            column=1, row=9, columnspan=2, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        self.peak_chart = PeakChart(self)

    def update_peak_plot(self, peaks: list[Any]) -> None:
        """
        Updates the bar plots for peak values.
        """
        self.peak_chart.update(peaks)

    def update_stats(
        self,
        detection: proto_data.Detection | None = None,
        heading: proto_heading.HeadingData | None = None,
        packet_time: Timestamp | None = None,
    ) -> None:
        rad_to_deg = lambda x: (
            normalize_angle(x * 180 / np.pi, high=360.0, low=0.0)
            if x is not None
            else 0
        )

        self.df_value_string.set(
            f"{rad_to_deg(detection.azimuth):.2f}°" if detection else None
        )
        self.df_value_mean_string.set(
            f"{rad_to_deg(detection.mean_azimuth):.2f}°" if detection else None
        )
        self.df_value_deviation_string.set(
            f"{rad_to_deg(detection.deviation):.2f}°" if detection else None
        )

        self.df_elev_string.set(
            f"{rad_to_deg(detection.elevation):.2f}°" if detection else None
        )
        self.df_elev_mean_string.set(
            f"{rad_to_deg(detection.mean_elevation):.2f}°" if detection else None
        )
        self.df_elev_deviation_string.set(f"TBD")

        self.snr_string.set(f"{detection.snr:.2f}") if detection else None

        (
            self.frequency_string.set(f"{detection.frequency / 1e6:.4f}M")
            if detection
            else None
        )
        (
            self.bandwidth_string.set(f"{detection.bandwidth / 1e6:.4f}M")
            if detection
            else None
        )

        if heading is not None:
            self.lat_string.set(f"{heading.gps_lat:.5f}°")
            self.lon_string.set(f"{heading.gps_lon:.5f}°")
            self.altitude_string.set(f"{heading.altitude:.2f} m ")
            if len(heading.quaternion) == 4:
                # Scipy's Rotation uses [x, y, z, w] order for quaternions
                # pyquaternion's yaw_pitch_roll() seems to be wrong so I used Scipy
                try:
                    attitude = Rotation.from_quat(
                        heading.quaternion[1:] + heading.quaternion[:1]
                    )
                    yaw, pitch, roll = attitude.as_euler("ZYX", degrees=True)
                except:
                    yaw, pitch, roll = "", "", ""
                    pass  # eg. 0-norm quaternion

                self.yaw_string.set(f"{yaw:.2f}°")
                self.pitch_string.set(f"{pitch:.2f}°")
                self.roll_string.set(f"{roll:.2f}°")
        if packet_time is not None:
            self.packet_time_string.set(packet_time.ToDatetime())
