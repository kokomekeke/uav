import math
import re
import tkinter
import tkinter.font
from tkinter import ttk
from typing import Any

import numpy as np

from pysagax.util.mat import normalize_angle


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
        snr_disp.grid(column=3, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=3)

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

    def update_peak_plot(self, peaks: list[Any]) -> None:
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

    def update_stats(
        self, latest_roi_results: dict[str, Any], aggregated_roi_results: dict[str, Any]
    ) -> None:
        rad_to_deg = lambda x: normalize_angle(x * 180 / np.pi, high=360.0, low=0.0)

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
