import math
import tkinter
import numpy as np
from tkinter import ttk
from typing import Any, Callable, Optional

import matplotlib
from matplotlib import pyplot
from matplotlib.animation import FuncAnimation  # type: ignore
from matplotlib.backend_bases import KeyEvent  # type: ignore
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_tkagg import (  # type: ignore
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

import pysagax
from pysagax.df.lena_core_service import CoreServiceSpectrumPacket
from pysagax.source.source_manager import CoreServiceStatus
from pysagax.spot.calculate_df_corrected import calculate_df_corrected
import pysagax.message.data_pb2 as proto_data

# from pysagax.spotclient import Client, conf, calculate_df_corrected
from pysagax.ui.custom_widgets import EntryWithLabel, ToggleButton
from pysagax.ui.lena_matplotlib_graphs import (
    CompassGraph,
    CompassGraphWithDeviation,
    GraphParameters,
    MagnitudeSpectrumGraph,
    WaterfallMagnitudeGraph,
)
from pysagax.util.read_from_conf import read_from_conf


class PlotFrame(tkinter.Frame):
    def __init__(self, master, conf, root, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        from pysagax.spotclient import Client

        self.conf = conf
        self.client: Client = self.master.client

        self.root: Any = root

        self.fig: Optional[pyplot.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.canvas_toolbar: Optional[NavigationToolbar2Tk] = None

        self.params = GraphParameters()

        self.animation: Optional[matplotlib.animation.FuncAnimation] = None
        """
        Matplotlib FuncAnimation object for animating the graphs
        """

        self.redraw_canvas: bool = False
        """
        Indicates to the packet handler whether the canvas needs to be redrawn 
        """

        self.spectrum_graph_min_db = read_from_conf(
            self.conf, ["display", "spectrum_graph_min_db"], -120
        )

        self.fps = read_from_conf(self.conf, ["display", "fps"], 25)

        self.max_bin_count = read_from_conf(self.conf, ["display", "max_bin_count"], 1024)

        self.params.waterfall_size = read_from_conf(
            self.conf, ["display", "waterfall_size"], 200
        )  # Amount of spectrum lines to be displayed on the waterfall diagram.

        self.make_plots = read_from_conf(self.conf, ["display", "make_plots"], True)

        self.create_canvas()

    def create_canvas(self) -> None:
        """
        Creates matplotlib canvas for graph plots. Called when connecting to the client.
        """
        self.destroy_plot()

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
        self.magnitude_waterfall_graph.max_points = self.max_bin_count
        self.magnitude_waterfall_graph.initialize()

        # colorbar = self.fig_ref.colorbar(  # type: ignore
        #     self.magnitude_waterfall_graph.image, format=lambda x, _: f"{x:.0f}dB"
        # )     #TODO:show colorbar but keep waterfall and spectrum graphs the same width
        self.magnitude_waterfall_graph.make_plot()

        self.magnitude_spectrum_plot = self.fig_ref.add_subplot(
            grid_spec[0, 0], sharex=self.magnitude_waterfall_plot
        )
        self.magnitude_spectrum_graph = MagnitudeSpectrumGraph(
            self.magnitude_spectrum_plot, self.params
        )
        self.magnitude_spectrum_graph.vmin = self.spectrum_graph_min_db
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
            ]
            if graph is not None
        ]

        self.animation = FuncAnimation(
            self.fig_ref,
            self.update_imag,
            interval=int(1000 / self.fps),
            blit=True,
            cache_frame_data=False,
        )
        grid_spec.tight_layout(figure=self.fig_ref)
        grid_spec.update()

    def update_imag(self, frame_number: int) -> list[matplotlib.artist.Artist]:
        self.update_sensors_and_graphs()
        image_list = []
        for graph in self.graph_list:
            graph.update()
            image_list.extend(graph.collect_images())
        return image_list

    def click_handler(self, event: Any) -> None:
        if self.master.client.source_manager.cs_status == CoreServiceStatus.DISCONNECTED:
            return
        control_frame_ref = self.master.control_frame  ##Could be better?
        ##TODO: set roi span from graph
        ##TODO: show roi on spectrum graph even if it was set or modified in control frame
        ##TODO: don't excecute this code when not connected to CS
        if self.magnitude_spectrum_graph is None:
            return
        if event.inaxes == self.magnitude_spectrum_graph.plot:
            roi_span = pysagax.si_to_float(control_frame_ref.roi_span_entry.get())
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

            control_frame_ref.roi_center_entry.set(f"{roi_freq:.0f}")
            control_frame_ref.roi_threshold_entry.set(f"{roi_threshold:.0f}")
            control_frame_ref.roi_span_entry.set(f"{roi_span:.0f}")

    def update_sensors_and_graphs(self) -> None:
        assert self.df_graph is not None  ##TODO: assert for all or no compass graphs?

        ##TODO: graph df_value_std (and latest df_value??)
        self.df_graph.add_point(
            self.master.aggregated_roi_results["df_value_mean"],
            self.master.aggregated_roi_results["df_value_std"],
        )
        self.compass_graph.add_point(self.master.compass_heading)

        df_corrected = calculate_df_corrected(
            df_value=self.master.aggregated_roi_results["df_value_mean"],
            compass_heading=self.master.compass_heading,
        )

        self.compass_df_graph.add_point(df_corrected)

    def plot_spectrum_packet(
        self,
        spectrum,
        signal_db: float = 0.0,
        noise_db: float = 0.0,
    ) -> None:
        if self.make_plots == False:
            return
        
        #Decoding spectrum data
        data_type = spectrum.data_type
        np_data_type = {
            proto_data.Spectrum.DataType.INT16: np.dtype(np.int16),
            proto_data.Spectrum.DataType.INT8: np.dtype(np.int8),
            proto_data.Spectrum.DataType.FLOAT32: np.dtype(np.float32),
        }[data_type]
        spectrum_data = np.frombuffer(spectrum.data, np_data_type)
        bin_count = len(spectrum_data)
        center_frequency = spectrum.center_frequency
        iq_rate = spectrum.bandwidth

        if bin_count == 0 or iq_rate == 0:
            return
        if (
            self.redraw_canvas
            or bin_count
            != self.params.bin_count  # or restart if the dimensions change
            or center_frequency
            != self.params.center_frequency  # or restart if the axes change
            or iq_rate != self.params.iq_rate
        ):
            # Animation can be created, because at this point we know bin count and other properties
            # Also restart when bin count or any other parameter has changed
            self.params.bin_count = bin_count
            self.params.iq_rate = iq_rate
            self.params.center_frequency = center_frequency
            self.create_anim()
            self.redraw_canvas = False

        assert self.magnitude_waterfall_graph is not None
        assert self.magnitude_spectrum_graph is not None
        self.magnitude_waterfall_graph.add_data(spectrum_data)
        self.magnitude_spectrum_graph.add_data(spectrum_data)
        self.magnitude_spectrum_graph.signal_lvl = signal_db
        self.magnitude_spectrum_graph.noise_lvl = noise_db

    def destroy_plot(self) -> None:
        if self.fig is not None:
            self.fig.gca().cla()  # type: ignore
        if self.canvas is not None:  # Remove old widget if there is one
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
        if self.canvas_toolbar is not None:
            self.canvas_toolbar.destroy()
            self.canvas_toolbar = None

    def enable_plotting(self) -> None:
        self.make_plots = True
        self.redraw_canvas = True

    def disable_plotting(self) -> None:
        self.make_plots = False
        self.destroy_plot()

    def reconfigure_plots(
        self,
        spectrum_graph_min_db: float,
        fps: float,
        max_bin_count: int,
        waterfall_size: int,
    ) -> None:
        self.spectrum_graph_min_db = spectrum_graph_min_db
        self.fps = fps
        self.max_bin_count = max_bin_count
        self.params.waterfall_size = waterfall_size

        self.redraw_canvas = True

    def start_animation(self) -> None:
        if self.animation is not None:
            if self.animation.event_source is not None:
                self.animation.event_source.start()

    def stop_animation(self) -> None:
        """
        Stopping the animation without destroying the canvas to save CPU.
        Useful when disconnected
        """
        if self.animation is not None:
            if self.animation.event_source is not None:
                self.animation.event_source.stop()


class PlotSettingsFrame(tkinter.Frame):
    def __init__(self, master, plot_frame,
        send_commands_function: Callable[[str], None],
          conf, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.send_commands_function = send_commands_function

        self.plot_frame: PlotFrame = plot_frame
        self.conf = conf
        self.client: Client = (
            self.master.master.master.client
        )  ##??? Dont need client reference?

        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=2)

        make_plots_label = ttk.Label(self, text="Make plots:")
        make_plots_label.grid(column=0, row=0, sticky=tkinter.W, padx=5, pady=5)
        self.toggle_button = ToggleButton(
            self,
            self.on_action,
            self.off_action,
            default_value=self.plot_frame.make_plots,
        )
        self.toggle_button.grid(column=1, row=0)

        self.spectrum_graph_min_entry = EntryWithLabel(
            self,
            "Spectrum graph min dB:",
            0,
            1,
            read_from_conf(conf, ["display", "spectrum_graph_min_db"], -80),
            tkinter.DoubleVar,
        )

        self.fps_entry = EntryWithLabel(
            self,
            "FPS:",
            0,
            2,
            read_from_conf(conf, ["display", "fps"], -25),
            tkinter.DoubleVar,
        )

        self.max_bin_count_entry = EntryWithLabel(
            self,
            "Waterfall bin count:",
            0,
            3,
            read_from_conf(conf, ["display", "max_bin_count"], 1024),
            tkinter.IntVar,
        )

        self.waterfall_size_entry = EntryWithLabel(
            self,
            "Waterfall size:",
            0,
            4,
            read_from_conf(conf, ["display", "waterfall_size"], 200),
            tkinter.IntVar,
        )

        self.configure_plot_button = tkinter.Button(
            self, text="Configure Plot", command=self.configure_plot_commands
        )
        self.configure_plot_button.grid(
            column=2, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.mean_window_width_slider_variable = tkinter.DoubleVar(
            value=read_from_conf(conf, ["stats", "mean_window_width_seconds"], 0)
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
            column=1, row=6, sticky=tkinter.E + tkinter.W, padx=5, pady=5, columnspan=2
        )

        mean_window_width_label = tkinter.Label(self, text="Rolling avg window (s):")
        mean_window_width_label.grid(column=0, row=6, padx=5, pady=8, sticky=tkinter.S)
        
        spectrum_selector_label = tkinter.Label(self, text="Spectrum channel:")
        spectrum_selector_label.grid(column=0, row=7, padx=5, pady=8, sticky=tkinter.S)

        self.channel_spectrum_combo = ttk.Combobox(self, width=1)
        self.channel_spectrum_combo["values"] = [0, 1, 2, 3]
        self.channel_spectrum_combo.grid(column=1, row=7, padx=5, pady=8, sticky=tkinter.S)
        self.channel_spectrum_combo.bind(
            "<<ComboboxSelected>>", self.choose_spectrum_commands
        )
        self.channel_spectrum_combo.configure(state="disabled")


    def mean_window_width_slider_commands(self, event: Any) -> None:
        window_size = self.mean_window_width_slider_variable.get()
        self.client.mean_window_width_value.value = window_size

    def configure_plot_commands(self) -> None:
        """
        validate the parameters (and display on GUI) then hand them to PlotFrame
        """
        fps = self.fps_entry.get()
        if fps <= 0:
            fps = read_from_conf(self.conf, ["display", "fps"], 25)
            self.fps_entry.set(fps)

        max_bin_count = self.max_bin_count_entry.get()
        if max_bin_count <= 0:
            max_bin_count = read_from_conf(self.conf, ["display", "max_bin_count"], 1024)
            self.max_bin_count_entry.set(max_bin_count)

        waterfall_size = self.waterfall_size_entry.get()
        if waterfall_size <= 0:
            waterfall_size = read_from_conf(self.conf, ["display", "waterfall_size"], 200)
            self.waterfall_size_entry.set(waterfall_size)

        self.plot_frame.reconfigure_plots(
            spectrum_graph_min_db=self.spectrum_graph_min_entry.get(),
            fps=fps,
            max_bin_count=max_bin_count,
            waterfall_size=waterfall_size,
        )

    def on_action(self) -> None:
        """
        Turn on plotting
        """
        self.plot_frame.enable_plotting()

    def off_action(self) -> None:
        """
        Turn plotting off
        """
        self.plot_frame.disable_plotting()
        
    def choose_spectrum_commands(self, event: Any) -> None:
        pass #TODO: implement using protobuf
        # self.send_commands_function(
        #     f"DEBUG:SpectrumChannel! {self.channel_spectrum_combo.current()};"
        # )
