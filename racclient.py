#!/usr/bin/env python3

from datetime import datetime
import math
import multiprocessing
import queue
import re
import socket
import threading
from time import sleep
import tkinter
from tkinter import font  ##why this it needed?
from tkinter import ttk
import matplotlib 
import numpy as np
from typing import Any, Callable, Optional


from matplotlib import pyplot
from matplotlib.animation import FuncAnimation  # type: ignore
from matplotlib.backend_bases import KeyEvent, key_press_handler  # type: ignore
from matplotlib.backends.backend_tkagg import (  # type: ignore
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

from pysagax import (
    BaseConnection,
    StreamAndCompassProcess,
    WaterfallAngleGraph,
    WaterfallMagnitudeGraph,
    MagnitudeSpectrumGraph,
    CompassGraph,
    GraphParameters,
    CoreServicePacket, CoreServiceSpectrumPacket, CoreServiceEOFPacket, CoreServiceROIResultPacket,
    CoreServiceROILackOfSignalPacket, CoreServiceDebugPacket,
)
import pysagax


###TODO:REMOVE
class ExapmleFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client = self.master.client ##???


class ConnectFrame(tkinter.Frame): 
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client = self.master.client ##???

        compass_offset = -1         ##TODO: should be an argument of master.client?
        encoder_offset = np.pi      ##TODO: should be an argument of master.client?

        self.host_address = tkinter.StringVar(value="10.1.1.113")   ##TODO: should be here or in ClientWindow??
        self.encoder_port_string = tkinter.StringVar(value="COM6")  ##TODO: should be here or in ClientWindow??

        offset_frame = tkinter.Frame(self, )        
        offset_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.LEFT, pady=0, padx=(20, 0))
        compass_offset_label_label = tkinter.Label(offset_frame, text="Compass offset: ", font=tkinter.font.Font(size=8))
        compass_offset_label_label.grid(column=0, row=0, pady=0)
        self.compass_offset_label = tkinter.Label(offset_frame, text=f"{(compass_offset * 180 / np.pi):.2f}°", font=tkinter.font.Font(size=8))
        self.compass_offset_label.grid(column=1, row=0, pady=0)
        encoder_offset_label_label = tkinter.Label(offset_frame, text="Encoder offset: ", font=tkinter.font.Font(size=8))
        encoder_offset_label_label.grid(column=0, row=1, pady=0)
        self.encoder_offset_label = tkinter.Label(offset_frame, text=f"{(encoder_offset * 180 / np.pi):.2f}°", font=tkinter.font.Font(size=8))
        self.encoder_offset_label.grid(column=1, row=1, pady=0)

        self.set_offset_button = tkinter.Button(self, text="Set offsets", command=self.set_offsets)
        self.set_offset_button.pack(side=tkinter.LEFT)

        host_label = tkinter.Label(self, text="Spectrum channel:")
        host_label.pack(
        side=tkinter.LEFT, fill=tkinter.NONE, padx=(20, 5), pady=10, expand=False
        )

        # self.channel_spectrum_combo_string = 
        self.channel_spectrum_combo = ttk.Combobox(self, width=1)
        self.channel_spectrum_combo["values"] = [0, 1, 2, 3]
        self.channel_spectrum_combo.pack(side=tkinter.LEFT)
        self.channel_spectrum_combo.bind("<<ComboboxSelected>>", self.choose_spectrum_commands)
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

        self.encoder_port_entry = tkinter.Entry(self, textvariable=self.encoder_port_string, width=8)
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
        pass #TODO
       
    def choose_spectrum_commands(self, event):
        self.client.send_commands(f"DEBUG:SpectrumChannel! {self.channel_spectrum_combo.current()};")
           
class StatusFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        status_command_label_label = tkinter.Label(
            self,
            text="Command:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_command_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_command_label = tkinter.Label(
            self, text="Not connected", font=tkinter.font.Font(size=10)
        )
        self.status_command_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_stream_label_label = tkinter.Label(
            self,
            text="Stream:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_stream_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_stream_label = tkinter.Label(
            self, text="Not connected", font=tkinter.font.Font(size=10)
        )
        self.status_stream_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_compass_label_label = tkinter.Label(
            self,
            text="GPS/Compass:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_compass_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_compass_label = tkinter.Label(
            self, text="Not connected", font=tkinter.font.Font(size=10)
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
            self, text="Down", font=tkinter.font.Font(size=10)
        )
        self.status_map_server_label.pack(
            side=tkinter.LEFT, padx=5, pady=10, anchor="w"
        )

class ControlFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)
        
        self.client = self.master.master.client ##???

        ###TODO here or in ClientWindow???
        self.freq_string = tkinter.StringVar(value="371.5M")
        self.bw_string = tkinter.StringVar(value="0.5M")
        self.gain_string = tkinter.StringVar(value="80")  ##TODO: int instead of str
        self.bin_count_string = tkinter.StringVar(value="128")
        self.burst_stride_string = tkinter.StringVar(value="50000")
        self.roi_center_string = tkinter.StringVar(value="371.6M")
        self.roi_span_string = tkinter.StringVar(value="50k")
        self.roi_threshold_string = tkinter.StringVar(value="-40")
        self.source_file_path_string = tkinter.StringVar(value="")


        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=2)
        self.columnconfigure(3, weight=1)

        freq_entry_label = ttk.Label(self, text="Frequency:")
        freq_entry_label.grid(column=0, row=0, sticky=tkinter.W, padx=5, pady=5)

        self.freq_entry = ttk.Entry(self, textvariable=self.freq_string, width=11)
        self.freq_entry.grid(column=1, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        bw_entry_label = ttk.Label(self, text="Bandwidth:")
        bw_entry_label.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=5)

        self.bw_entry = ttk.Entry(self, textvariable=self.bw_string, width=11)
        self.bw_entry.grid(column=1, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        gain_entry_label = ttk.Label(self, text="USRP Gain:")
        gain_entry_label.grid(column=0, row=2, sticky=tkinter.W, padx=5, pady=5)

        self.gain_entry = ttk.Entry(self, textvariable=self.gain_string, width=11)
        self.gain_entry.grid(column=1, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=5)

        bin_count_entry_label = ttk.Label(
            self, text="Bin count:"
        )  # TODO:separate bin count and burst stride setting?
        bin_count_entry_label.grid(column=0, row=3, sticky=tkinter.W, padx=5, pady=5)

        bin_count_combo = ttk.Combobox(self, textvariable=self.bin_count_string, width=11)
        bin_count_combo["values"] = [
                                    # Virgin monetary scale values.
                                    200,
                                    500,
                                    1000,
                                    2000,
                                    5000,
                                    10000,
                                    #Chad power of 2 values.
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
                                    0x80000,]
        bin_count_combo.grid(
            column=1, row=3, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        roi_center_entry_label = ttk.Label(self, text="ROI center freq:")
        roi_center_entry_label.grid(column=2, row=0, sticky=tkinter.W, padx=5, pady=5)

        roi_center_entry = ttk.Entry(self, textvariable=self.roi_center_string, width=11)
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
        self.source_combo.grid(column=0, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5)
        self.source_combo.bind("<<ComboboxSelected>>", self.source_combo_update)
        
        
        self.source_file_path_combo = ttk.Combobox(
            self, textvariable=self.source_file_path_string, width=11, state='disabled'
        )
        self.source_file_path_combo.grid(
            column=1, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5, columnspan=3
        )

        

        self.start_button = tkinter.Button(
            self, text="Start", command=self.start_commands
        )
        self.start_button.grid(
            column=3, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.start_button.configure(state="disabled")

        self.rec_button = tkinter.Button(
            self, text="Rec", command=self.rec_commands
        )
        self.rec_button.grid(
            column=2, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.rec_button.configure(state="disabled")

    def start_commands(self):
        default_source_file_path = "/home/sagax/Generator/"
        if self.source_combo.current() == 1:
            source_file_path = default_source_file_path
        else:
            source_file_path = self.source_file_path_string.get()
        
        kwargs = {"freq": pysagax.si_to_float(self.freq_string.get()),
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
        self.client.start_commands(**kwargs)

    def rec_commands():
        pass

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

class StatFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client = self.master.master.client ##???

        ##TODO
        self.df_value_string = tkinter.StringVar(value="NaN")
        self.df_value_mean_string = tkinter.StringVar(value="NaN")
        self.df_value_deviation_string = tkinter.StringVar(value="NaN")
        self.df_value_rms_string = tkinter.StringVar(value="NaN")


        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        disp_font = tkinter.font.Font(family="serif", size=14)

        df_value_label = ttk.Label(self, text="DF angle:")
        df_value_label.grid(column=0, row=0, sticky=tkinter.W, padx=5, pady=5)
        df_value_disp = ttk.Label(
            self,
            textvariable=self.df_value_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        df_value_disp.grid(column=1, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=3)


        ##TODO: stats
        """ mean_disp_label = ttk.Label(self, text="DF mean:")
        mean_disp_label.grid(column=0, row=0, sticky=tkinter.W, padx=5, pady=5)
        mean_disp = ttk.Label(
            self,
            textvariable=self.df_value_mean_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        mean_disp.grid(column=1, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=3)

        deviation_disp_label = ttk.Label(self, text="DF deviation:")
        deviation_disp_label.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=3)
        deviation_disp = ttk.Label(
            self,
            textvariable=self.df_value_deviation_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        deviation_disp.grid(
            column=1, row=1, sticky=tkinter.E + tkinter.W, padx=5, pady=3
        )

        rms_disp_label = ttk.Label(self, text="DF RMS error:")
        rms_disp_label.grid(column=0, row=2, sticky=tkinter.W, padx=5, pady=3)
        rms_disp = ttk.Label(
            self,
            textvariable=self.df_value_rms_string,
            font=disp_font,
            foreground="red",
            background="yellow",
        )
        rms_disp.grid(column=1, row=2, sticky=tkinter.E + tkinter.W, padx=5, pady=3)
         """
        self.peak_chart = tkinter.Canvas(
            self,
            bg="white",
            bd=0,
            highlightthickness=2,
            highlightbackground="black",
            height=109,
        )
        self.peak_chart.grid(
            column=0, row=4, columnspan=2, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )
        self.peak_bars = [
            self.peak_chart.create_rectangle(2, 7, 100, 27, fill="yellow"),
            self.peak_chart.create_rectangle(2, 32, 100, 52, fill="dodger blue"),
            self.peak_chart.create_rectangle(2, 57, 100, 77, fill="green"),
            self.peak_chart.create_rectangle(2, 82, 100, 102, fill="red"),
        ]
        self.peak_texts = [
            self.peak_chart.create_text(
                30, 17, text="32555", fill="black", font=("Helvetica 13 bold")
            ),
            self.peak_chart.create_text(
                30, 42, text="32555", fill="black", font=("Helvetica 13 bold")
            ),
            self.peak_chart.create_text(
                30, 67, text="32555", fill="black", font=("Helvetica 13 bold")
            ),
            self.peak_chart.create_text(
                30, 92, text="32555", fill="black", font=("Helvetica 13 bold")
            ),
        ]

    def update_peak_plot(self, peaks: list) -> None:
        """
        Updates the bar plots for peak values.
        """
        max_width = self.peak_chart.winfo_width()
        adc_resolution = 2**15 - 1

        peaks_dbfs = [20 * math.log10(int(peak) / adc_resolution) for peak in peaks]
        min_dbfs_level = 20 * math.log10(
            400 / adc_resolution
        )  # min value of the scale (aprox. noise level)
        bar_widths = [
            2 + (1 - peak / min_dbfs_level) * (max_width - 4) for peak in peaks_dbfs
        ]  # logarithmic scaling

        self.peak_chart.coords(self.peak_bars[0], 2, 7, bar_widths[0], 27)
        self.peak_chart.coords(self.peak_bars[1], 2, 32, bar_widths[1], 52)
        self.peak_chart.coords(self.peak_bars[2], 2, 57, bar_widths[2], 77)
        self.peak_chart.coords(self.peak_bars[3], 2, 82, bar_widths[3], 102)

        for i in range(4):
            text = re.sub (r"^-(0\.?0*)$", r"\1", f"{peaks_dbfs[i]:.0f}")   #formatting numbers rounded to -0 to +0
            self.peak_chart.itemconfig(self.peak_texts[i], text=text)

class PlotFrame(tkinter.Frame):
    def __init__(self, master, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.client = self.master.client ##???

        self.fig: Optional[pyplot.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.canvas_toolbar: Optional[NavigationToolbar2Tk] = None

        
        self.params = GraphParameters()
        #self.params.waterfall_size = args.wf    #Amount of spectrum lines to be displayed on the waterfall diagram.
        self.params.waterfall_size = 200 ##TODO: get from params

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
        
        root.update()   #this solves matplotlib artifacts?

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
        ).initialize()
        # colorbar = self.fig_ref.colorbar(  # type: ignore
        #     self.magnitude_waterfall_graph.image, format=lambda x, _: f"{x:.0f}dB"
        # )
        self.magnitude_waterfall_graph.make_plot()

        self.magnitude_spectrum_plot = self.fig_ref.add_subplot(grid_spec[0, 0])
        self.magnitude_spectrum_graph = MagnitudeSpectrumGraph(self.magnitude_spectrum_plot, self.params)
        self.magnitude_spectrum_graph.vmin = -80
        self.magnitude_spectrum_graph.initialize(color="blue").make_plot()

        self.fig_ref.canvas.callbacks.connect("button_press_event", self.click_handler)  # type: ignore

        self.compass_plot = self.fig_ref.add_subplot(
            grid_spec[1, 1], projection="polar"
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

        self.encoder_graph = CompassGraph(self.compass_plot, self.params).initialize(
            "green", "Encoder Heading"
        )

        self.compass_plot.legend(loc='upper left', bbox_to_anchor=(1,1.1))
        self.df_plot.legend(loc='upper left', bbox_to_anchor=(1,1))

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

        # self.animation = FuncAnimation(
        #     self.fig_ref, self.update_imag, interval=int(1000 / args.fps), blit=True
        # )     ###TODO: args
        self.animation = FuncAnimation(
            self.fig_ref, self.update_imag, interval=int(1000 / 30), blit=True
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
        control_frame_ref = self.client.client_window.control_frame ##Could be better?
        ##TODO: set roi span from graph
        ##TODO: show roi on spectrum graph even if it was set or modified in control frame
        ##TODO: don't excecute this code when not connected to CS
        if self.magnitude_spectrum_graph is None:
            return
        if event.inaxes == self.magnitude_spectrum_graph.plot:
            roi_span = pysagax.si_to_float(control_frame_ref.roi_span_string.get())
            roi_freq = self.magnitude_spectrum_graph.coord_to_freq(event.xdata)
            roi_threshold = event.ydata

            self.client.update_roi_settings(roi_freq, roi_span, math.floor(roi_threshold))

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
        """ dfg_map_server.update_timestamp()
                dfg_map_server.update_angle(df_corrected, 1e6)
            else:
                self.compass_df_graph.add_point(None)

        if (
            compass is not None
            and compass.parser.lat is not None
            and compass.parser.lon is not None
        ):
            dfg_map_server.update_lat_lon(compass.parser.lat, compass.parser.lon) """
        


        assert self.df_graph is not None    ##TODO: assert for all or no compass graphs?
        self.df_graph.add_point(self.master.df_value)

        self.compass_graph.add_point(self.master.compass_heading)
        if self.master.compass_heading is not None:
            df_corrected = pysagax.normalize_angle(self.master.compass_heading + self.master.df_value)  
            self.compass_df_graph.add_point(df_corrected)
        else:   #Can we do it without the if-else?
            self.compass_df_graph.add_point(None)
        
        self.encoder_graph.add_point(self.master.encoder_heading)

    def plot_spectrum_packet(self, packet: CoreServiceSpectrumPacket) -> None:
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
        ###self.log_octave_data()

class ClientWindow(tkinter.Frame):
    def __init__(self, client, root):
        self.do_stop = False

        #Last measured angles for the matplotlib animation in plot_frame:
        self.df_value = None
        self.compass_angle = None
        self.compass_heading = None     #compass angle corrected with offset
        self.encoder_angle = None
        self.encoder_heading = None     #encoder angle corrected with offset

        tkinter.Frame.__init__(self, root)
        self.pack(side="top", fill=tkinter.BOTH, expand=True)

        self.client = client    #The GUI communicates with other components of the client through this reference

        self.status_frame = StatusFrame(self, relief=tkinter.RAISED, borderwidth=1)
        self.status_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        self.connect_frame = ConnectFrame(self, relief=tkinter.RAISED, borderwidth=1)
        self.connect_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        self.plot_frame = PlotFrame(self)
        self.plot_frame.create_canvas()
        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)  ##TODO: this was after bottom_frame.pack(). Should it be there?

        self.bottom_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)    ##TODO: frames inside this will be one level deeper than connect and status frames. is it OK??
        self.bottom_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        
        self.control_frame = ControlFrame(self.bottom_frame, relief=tkinter.RAISED, borderwidth=1)        
        self.control_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.LEFT)

        self.center_notebook = ttk.Notebook(self.bottom_frame)
        self.tab1 = ttk.Frame(self.center_notebook) 
        self.stream_packets_tab = ttk.Frame(self.center_notebook)
        self.center_notebook.add(self.tab1, text="Status info")
        self.center_notebook.add(self.stream_packets_tab, text="Stream packets")
        self.center_notebook.pack(side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True)

        self.status_info_lb = tkinter.Listbox(self.tab1, height=4, width=75)
        self.status_info_lb.pack(side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True)

        self.stream_packets_lb = tkinter.Listbox(self.stream_packets_tab, height=4, width=75)
        self.stream_packets_lb.pack(side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True)

        self.stat_frame = StatFrame(self.bottom_frame, relief=tkinter.RAISED, borderwidth=1, width=600)
        self.stat_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.RIGHT)

        self.packet_handler_thread = threading.Thread(target=self.gui_packet_handler, daemon=True).start()

    def gui_packet_handler(self):
        while not self.do_stop:
            try:
                data = self.client.stream_to_gui_queue.get(timeout=0.2)

                packet = data["cs_packet"]
                self.compass_angle = data["compass_angle"]
                self.compass_heading = data["compass_heading"]
                self.encoder_angle = data["encoder_angle"]
                self.encoder_heading = data["encoder_heading"]

                try:
                    ts = datetime.fromtimestamp(packet.time_ns / 1e9, tz=None)
                    packet_string = (f"[{packet.stream_id}] {ts.strftime('%H:%M:%S')}.{int((packet.time_ns % 1e9) / 1e6):03d} - "
                                    f"{str(packet)} - c_angle={self.compass_angle}; e_angle={self.encoder_angle}")
                    self.stream_packets_lb.insert(tkinter.END, packet_string)
                    self.stream_packets_lb.delete(0, self.stream_packets_lb.size() - 1000)
                    self.stream_packets_lb.see(tkinter.END)
                    
                    if isinstance(packet, CoreServiceSpectrumPacket):  
                        self.plot_frame.plot_spectrum_packet(packet)

                    if isinstance(packet, CoreServiceDebugPacket):  #updating peak plots
                        if packet.title == "peaks":
                            regex = r"peak(\d+)=(\d+)"
                            matches = re.findall(
                            regex, str(packet)
                            )  # creating a list of (ChannelID, PeakValue) tuples from the debug message
                            peaks = [peak[1] for peak in matches]
                            self.stat_frame.update_peak_plot(peaks)

                    if isinstance(packet, CoreServiceROIResultPacket):
                        self.df_value = packet.roi_azimuth
                        df_value_deg = self.df_value  * 180/np.pi
                        if df_value_deg < 0:
                            df_value_deg += 360
                        self.stat_frame.df_value_string.set(f"{df_value_deg:.2f}°")
                    
                    if isinstance(packet, CoreServiceEOFPacket):
                        self.update_status_info("End of filed reached for Sigmf recording", source="GUI packet handler")
                except Exception as e:
                    print("[GUI packet handler]", e)
            except queue.Empty:
                pass
            except Exception as e:
                print("[GUI packet handler]", e)
                return

    def set_stream_status(self, message: str) -> None:
        try:
            self.status_frame.status_stream_label.config(text=message)
        except:
            pass ##TODO: when exiting, this gets called after the window no longer exists
    
    def set_command_status(self, message: str) -> None:
        try:
            self.status_frame.status_command_label.config(text=message)
        except:
            pass ##TODO: when exiting, this gets called after the window no longer exists

    def connect_commands(self):
        connect_action = self.connect_action
        disconnect_action = self.disconnect_action
        host_address = self.connect_frame.host_address.get()
        encoder_port = self.connect_frame.encoder_port_string.get()
        self.client.connect_commands(connect_action, disconnect_action, host_address, encoder_port)
        
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

        self.control_frame.start_button.configure(state="normal")
        # self.control_frame.rec_button.configure(state="normal")

        try:    ##TODO: move this from GUI thread
            path_list = b""
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.connect_frame.host_address.get(), 12939))   ##TODO port no. to args
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
                print("[Connect action - MPL animation]", e)

    def disconnect_action(self) -> None:
        """
        Events triggered by client disconnect
        """
        try:
            self.connect_frame.disconnect_button.configure(state="disabled")
            self.connect_frame.host_entry.configure(state="normal")
            self.connect_frame.connect_button.configure(state="normal")
            self.connect_frame.channel_spectrum_combo.configure(state="disabled")

            self.control_frame.start_button.configure(state="disabled")
            self.control_frame.rec_button.configure(state="disabled")

            self.disconnect_commands()  # to disconnect the other thread
        except RuntimeError:
            pass  # it might happen when closing the window
        try:
            self.plot_frame.animation.event_source.stop()
        except Exception as e:
            print("[Disconnect action - MPL animation]", e)

    def update_status_info(self, update_string: str|list[str], source: str=None):
        if not isinstance(update_string, list):
            update_string = [update_string]
        for line in update_string:
            if source is not None:
                line = f"[{source}]: {line}"
            self.status_info_lb.insert(tkinter.END, line)
            self.status_info_lb.delete(0, self.stream_packets_lb.size() - 1000)
            self.status_info_lb.see(tkinter.END)

class CommandsConnectionThread(BaseConnection, threading.Thread):
    def __init__(self, client) -> None:
        BaseConnection.__init__(self)
        threading.Thread.__init__(self, daemon=True)
        self.incoming_buffer: bytearray = bytearray()
        self.status_text: str = ""
        self.incoming_messages_queue: queue.Queue[str] = queue.Queue()

        self.client = client

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
        self.client.command_status_msg_handler(message)

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.disconnect = False
        self.run_socket()
    
    def send_commands(self, cmd: str) -> None:
        """
        Send the command from the command entry box to the client. Called on pressing the Return key in the autocomplete box.
        """
        cmd = cmd.replace("\n", "").replace("\r", "")
        error_msg = []
        for cmd_line in cmd.split(";"):  # One command per line
            if not cmd_line:
                continue
            cmd_line = cmd_line.strip()
            cmd_line += ";"
            self.client_socket.send(cmd_line.encode())
            
            try:
                response = self.incoming_messages_queue.get(
                    block=True, timeout=30
                )
                response_parts = response.split(" ")
                error_code = int(response_parts[0])
                if error_code:
                    error_msg.append(f"Error with command \"{cmd_line}\": {response}")
            except queue.Empty:
                print("Timeout", f"Command {cmd_line} timed out.")
            sleep(0.1)
        if error_msg:
            self.client.status_update_handler(error_msg, source="Command thread")
        else:
            self.client.status_update_handler("Core Service configured", source="Command thread")


class TestStreamDisplayThread(threading.Thread):
    def __init__(self, client) -> None:
        super().__init__()

        self.client = client

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

        self.compass_host_port = ""
        self.encoder_port = ""

    def status_watcher_thread(self, status_queue: queue.Queue[str]) -> None:
        """
        Entry point of the watcher thread
        """
        while True:
            try:
                terminate = False
                while not status_queue.empty():
                    message = status_queue.get(
                        timeout=0.2
                    )  # get status message from stream process
                    if message == "END":
                        terminate = True
                    else:
                        self.client.stream_status_msg_handler(message)
                self.disconnect_value.value = self.disconnect
                if terminate:
                    print("[StreamAndCompassProcess]", message)
                    break
            except queue.Empty:
                pass
            except BrokenPipeError:
                return
            except RuntimeError:
                return  # it might happen on the UI when closing the window
            sleep(0.2)
        

    def run(self) -> None:
        """
        Entry point of the data handling thread
        """

        global args
        status_queue: multiprocessing.Queue[str] = multiprocessing.Queue()
        """
        The string elements of the status queue are the messages to be displayed on the GUI status bar
        """

        # The purpose of the watcher thread is to take the status messages from the multiprocessing process and display
        # them on the GUI, and to forward the disconnect signal to the process if the "Disconnect" button is clicked.
        watcher_thread = threading.Thread(
            target=self.status_watcher_thread,
            args=[status_queue],
            daemon=True,
        )
        watcher_thread.start()

        packets_queue: multiprocessing.Queue[
            tuple[float, CoreServicePacket]
        ] = multiprocessing.Queue()
        """
        This queue will transfer the processed packets from the stream process to the main (GUI) process
        """

        stream_process = StreamAndCompassProcess(
            [packets_queue, self.client.stream_to_gui_queue], self.disconnect_value, status_queue
        )

        stream_process.host_port = self.host_port
        stream_process.compass_host_port = self.compass_host_port
        stream_process.encoder_port = self.encoder_port
        stream_process.start()

        # The code below will handle the preprocessed packets from the stream process
        while True:
            if self.disconnect or not watcher_thread.is_alive():
                break
            try:
                data = packets_queue.get(timeout=0.5)  # get a packet from the stream process
                
                packet = data["cs_packet"]
                compass_angle = data["compass_angle"]
                encoder_angle = data["encoder_angle"]
            except queue.Empty:
                continue
            
            ##TODO: proper packet handling
            ##TODO: handlers
            """ next(
                handler
                for packet_class, handler in self.packet_handlers.items()
                if isinstance(packet, packet_class)
            )(packet) """

        self.disconnect_value.value = True
        stream_process.join()
        stream_process.terminate()


#Owner class for the client
class Client:
    def __init__(self, root):

        self.stream_to_gui_queue: multiprocessing.Queue[dict] = multiprocessing.Queue()

        self.client_window = ClientWindow(self,  root)
        self.command_thread = None
        self.stream_thread = None
        self.logger_process = None
        self.dfg_map_server = None
        self.encoder_thread = None

    def send_commands(self, cmd: str) -> None:        
        """
        Send the command from the command entry box to the client. Called on pressing the Return key in the autocomplete box.
        """
        assert self.command_thread
        assert self.command_thread.client_socket
        if self.command_thread is None:     ##TODO: After disconnecting command_thread should be None
            return
        thread = threading.Thread(target=self.command_thread.send_commands, args=(cmd,), daemon=True)
        thread.start()

    def connect_commands(self, connect_action, disconnect_action, host_address, encoder_port: str = "") -> None:
        """
        Action of the "Connect" button
        """
        self.command_thread = CommandsConnectionThread(self)
        self.command_thread.connect_action = connect_action
        self.command_thread.disconnect_action = disconnect_action
        self.command_thread.host_port = f"{host_address}:12936"
        self.command_thread.start()

        

        self.stream_thread = TestStreamDisplayThread(self)
        self.stream_thread.host_port = f"{host_address}:12937"
        self.stream_thread.compass_host_port = f"{host_address}:12938"
        self.stream_thread.encoder_port = encoder_port
        self.stream_thread.start()

    def start_commands(self, freq, bw, gain, bin_count, burst_stride, roi_center, roi_span, roi_threshold, from_file, source_file_path) -> None:
        connect_string = 'UHD "serial=8001680,serial=8001820" "A:A A:B"'      # for 10.1.1.113 (RAC setup)
        # connect_string = 'UHD "serial=8002051,serial=8002065" "A:A A:B"'  # for 10.1.1.139 (aron)

        if from_file:
            if source_file_path[-1] != "/":
                source_file_path = source_file_path + "/"
            self.send_commands(
                f'SOURCE:Path! SigMF "{source_file_path}recording.sigmf-collection";' 
                f"SOURCE:Position! 0;"  
                f"AOA:BinCount! {bin_count};"
                f"SOURCE:BurstStride! {burst_stride};"
                f"SOURCE:Configure!;"
                f"AOA:Configure!;"
                f"SOURCE:Start!;"
                f"ROI:Enable! 1;"            
                f"ROI:CenterFrequency! {roi_center:.0f};"
                f"ROI:Span! {roi_span:.0f};"
                f"ROI:Threshold! {roi_threshold};"
                f"ROI:Configure!;"
                f"DEBUG:Enable! exportPhaseDiffs;"
            )
        else:
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
                f"ROI:CenterFrequency! {roi_center:.0f};"
                f"ROI:Span! {roi_span:.0f};"
                f"ROI:Threshold! {roi_threshold};"
                f"ROI:Configure!;"
                f"DEBUG:Enable! exportPhaseDiffs;"
            )

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

        #TODO: properly make these threads stop after disconnect
        """ self.command_thread.join()
        self.stream_thread.join() """

    def update_roi_settings(self, roi_center, roi_span, roi_threshold):
        self.send_commands(
            f"ROI:CenterFrequency! {roi_center:.0f};"
            f"ROI:Span! {roi_span:.0f};"
            f"ROI:Threshold! {roi_threshold:.0f};"
            f"ROI:Configure!;"
        )    

    def stream_status_msg_handler(self, message):
        threading.Thread(target=self.client_window.set_stream_status, args=(message,), daemon=True).start()

    def command_status_msg_handler(self, message):
        threading.Thread(target=self.client_window.set_command_status, args=(message,), daemon=True).start()
    
    def status_update_handler(self, update_string: str|list[str], source: str=None):
        threading.Thread(target=self.client_window.update_status_info, args=(update_string, source), daemon=True).start()

def on_close():
    global run_threads
    # dfg_map_server.run_thread = False
    ex.client_window.do_stop = True
    ex.disconnect_commands()
    run_threads = False
    root.destroy()

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = Client(root)
    root.geometry("1200x850")
    root.wm_title(f"Sagax Direction Finder Client Application {pysagax.__version__}")
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
