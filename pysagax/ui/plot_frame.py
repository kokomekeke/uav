import tkinter
from tkinter import ttk
from typing import Any, Optional
import matplotlib
import math
from matplotlib import pyplot
from matplotlib.animation import FuncAnimation  # type: ignore
from matplotlib.backend_bases import KeyEvent  # type: ignore
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_tkagg import (  # type: ignore
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

import pysagax

# from pysagax.spotclient import Client, conf, calculate_df_corrected
from pysagax import (
    CompassGraph,
    CompassGraphWithDeviation,
    CoreServiceSpectrumPacket,
    GraphParameters,
    MagnitudeSpectrumGraph,
    WaterfallMagnitudeGraph,
)
from pysagax.ui.custom_widgets import ToggleButton, EntryWithLabel


class PlotFrame(tkinter.Frame):
    def __init__(self, master, conf, root, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        global calculate_df_corrected
        from pysagax.spotclient import Client, calculate_df_corrected

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

        self.animation_started: bool = False
        """
        Indicates whether the animation and plot objects have been created
        """

        self.spectrum_graph_min_db = (
            self.conf["display"]["spectrum_graph_min_db"] if self.conf else -120
        )

        self.fps = self.conf["display"]["fps"] if self.conf else 25

        self.max_bin_count = (
            self.conf["display"]["max_bin_count"] if self.conf else 1024
        )

        self.params.waterfall_size = (
            self.conf["display"]["waterfall_size"] if self.conf else 200
        )  # Amount of spectrum lines to be displayed on the waterfall diagram.

        self.make_plots = self.conf["display"]["make_plots"] if self.conf else True

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

        self.animation = FuncAnimation(
            self.fig_ref, self.update_imag, interval=int(1000 / self.fps), blit=True
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
        self.encoder_graph.add_point(self.master.encoder_heading)

        df_corrected = calculate_df_corrected(
            df_value=self.master.aggregated_roi_results["df_value_mean"],
            compass_heading=self.master.compass_heading,
            encoder_heading=self.master.encoder_heading,
        )

        self.compass_df_graph.add_point(df_corrected)

    def plot_spectrum_packet(
        self,
        packet: CoreServiceSpectrumPacket,
        signal_db: float = 0.0,
        noise_db: float = 0.0,
    ) -> None:
        if self.make_plots == False:
            return
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

    def destroy_plot(
        self,
    ) -> None:
        if self.fig is not None:
            self.fig.gca().cla()  # type: ignore
        if self.canvas is not None:  # Remove old widget if there is one
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
        if self.canvas_toolbar is not None:
            self.canvas_toolbar.destroy()
            self.canvas_toolbar = None

        self.animation_started = False


class PlotSettingsFrame(tkinter.Frame):
    def __init__(self, master, plot_frame, conf, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.plot_frame: PlotFrame = plot_frame
        self.conf = conf
        self.client: Client = (
            self.master.master.master.client
        )  ##??? Dont need client reference?

        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=2)
        self.columnconfigure(3, weight=1)

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
            (conf["display"]["spectrum_graph_min_db"] if conf else -80),
            tkinter.DoubleVar,
        )

        self.fps_entry = EntryWithLabel(
            self,
            "FPS:",
            0,
            2,
            (conf["display"]["fps"] if conf else -25),
            tkinter.DoubleVar,
        )

        self.max_bin_count_entry = EntryWithLabel(
            self,
            "Waterfall bin count:",
            0,
            3,
            (conf["display"]["max_bin_count"] if conf else 1024),
            tkinter.IntVar,
        )

        self.waterfall_size_entry = EntryWithLabel(
            self,
            "Waterfall size:",
            0,
            4,
            (conf["display"]["waterfall_size"] if conf else 200),
            tkinter.IntVar,
        )

        self.configure_plot_button = tkinter.Button(
            self, text="Configure Plot", command=self.configure_plot_commands
        )
        self.configure_plot_button.grid(
            column=3, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )

    def configure_plot_commands(self):
        self.plot_frame.spectrum_graph_min_db = self.spectrum_graph_min_entry.get()

        fps = self.fps_entry.get()
        if fps <= 0:
            fps = self.conf["display"]["fps"]
            self.fps_entry.set(fps)
        self.plot_frame.fps = fps

        max_bin_count = self.max_bin_count_entry.get()
        if max_bin_count <= 0:
            max_bin_count = self.conf["display"]["max_bin_count"]
            self.max_bin_count_entry.set(max_bin_count)
        self.plot_frame.max_bin_count = max_bin_count

        waterfall_size = self.waterfall_size_entry.get()
        if waterfall_size <= 0:
            waterfall_size = self.conf["display"]["waterfall_size"]
            self.waterfall_size_entry.set(waterfall_size)
        self.plot_frame.params.waterfall_size = waterfall_size

        self.plot_frame.animation_started = False  # Forces the redrawing of plots

    def on_action(self) -> None:
        """
        Turn on plotting
        """
        self.plot_frame.make_plots = True

    def off_action(self) -> None:
        """
        Turn plotting off
        """
        self.plot_frame.make_plots = False
        self.plot_frame.animation_started = False
        try:
            self.plot_frame.animation.event_source.stop()
        except:
            pass
        self.plot_frame.destroy_plot()
