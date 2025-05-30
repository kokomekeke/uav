from math import floor, ceil
import tkinter
import matplotlib.gridspec
import numpy as np
from tkinter import ttk
from typing import Any, Callable, Optional
import logging

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
from pysagax.source.source_manager import CoreServiceStatus
from pysagax.spot.calculate_df_corrected import calculate_df_corrected
from pysagax.field.scanengine import ScanEngineState
import pysagax.message.data_pb2 as proto_data
import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.heading_pb2 as proto_heading
from pysagax.util.run_once import run_once

# from pysagax.spotclient import Client, conf, calculate_df_corrected
from pysagax.ui.custom_widgets import EntryWithLabel, ToggleButton
from pysagax.ui.lena_matplotlib_graphs import (
    CompassGraph,
    CompassGraphWithDeviation,
    GraphParameters,
    MagnitudeSpectrumGraph,
    MagnitudeSpectrumGraphWithRoiMask,
    WaterfallMagnitudeGraph,
)
from pysagax.util.mat import yaw_pitch_roll_from_quaternion
from pysagax.util.read_from_conf import read_from_conf
from pysagax.util.protobuf_spectrum_utils import protobuf_spectrum_to_numpy


class PlotFrame(tkinter.Frame):
    def __init__(self, master, conf, root, roi_click_handler_function, *args, **kwargs):
        tkinter.Frame.__init__(self, master, *args, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)

        from pysagax.spotclient import Client

        self.conf = conf
        self.client: Client = self.master.client

        self.roi_click_handler_function = roi_click_handler_function

        self.root: Any = root

        self.fig: Optional[pyplot.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.canvas_toolbar: Optional[NavigationToolbar2Tk] = None

        self.params: list[GraphParameters] = []

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

        self.max_bin_count = read_from_conf(
            self.conf, ["display", "max_bin_count"], 1024
        )

        self.make_plots = read_from_conf(self.conf, ["display", "make_plots"], True)

        self.create_canvas()
        self._draw_empty_plot()

    def _draw_empty_plot(self) -> None:
        # this gets called on startup to fill the graph area with an empty plot
        spectrum = proto_data.Spectrum()
        spectrum.spectrum_type = proto_data.Spectrum.SpectrumType.MAGNITUDE
        spectrum.data_type = proto_data.Spectrum.DataType.INT16
        spectrum.channel_id = 0
        spectrum.data = np.array([0, 0, 0]).astype(np.dtype(np.int16)).tobytes()
        spectrum.center_frequency = 2
        spectrum.bandwidth = 1
        self.plot_spectrum_packet(spectrum=spectrum)
        self.start_animation()

    def create_canvas(self) -> None:
        """
        Creates matplotlib canvas for graph plots. Called when connecting to the client.
        """
        self.destroy_plot()

        # constrained -> small outer margins; tight -> aligned x axis in plots
        # TODO: achieve the pros of constrained and tight at the same time
        self.fig = pyplot.Figure(layout="constrained")
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
        # sort params (and graphs) by center freq
        self.params.sort(key=lambda p: p.center_frequency)

        assert self.fig_ref
        self.fig_ref.clf()

        grid_spec = self.fig_ref.add_gridspec(  # type: ignore
            nrows=2,
            ncols=2,
            width_ratios=(10, 2),
            height_ratios=(1, 1),
            wspace=0.01,
            hspace=0.01,
        )

        waterfall_grid_spec = matplotlib.gridspec.GridSpecFromSubplotSpec(
            1, len(self.params), subplot_spec=grid_spec[1, 0], wspace=0.01, hspace=0.01
        )
        spectrum_grid_spec = matplotlib.gridspec.GridSpecFromSubplotSpec(
            1, len(self.params), subplot_spec=grid_spec[0, 0], wspace=0.01, hspace=0.01
        )
        self.magnitude_waterfall_plot = []
        self.magnitude_waterfall_graph = []
        self.magnitude_spectrum_plot = []
        self.magnitude_spectrum_graph = []
        for i in range(len(self.params)):
            self.magnitude_waterfall_plot.append(
                self.fig_ref.add_subplot(waterfall_grid_spec[i])
            )
            self.magnitude_waterfall_graph.append(
                WaterfallMagnitudeGraph(
                    self.magnitude_waterfall_plot[i], self.params[i]
                )
            )
            self.magnitude_waterfall_graph[i].max_points = self.max_bin_count
            self.magnitude_waterfall_graph[i].initialize()

            # colorbar = self.fig_ref.colorbar(  # type: ignore
            #     self.magnitude_waterfall_graph.image, format=lambda x, _: f"{x:.0f}dB"
            # )     #TODO:show colorbar but keep waterfall and spectrum graphs the same width
            self.magnitude_waterfall_graph[i].make_plot()

            self.magnitude_spectrum_plot.append(
                self.fig_ref.add_subplot(
                    spectrum_grid_spec[i], sharex=self.magnitude_waterfall_plot[i]
                )
            )
            self.magnitude_spectrum_graph.append(
                MagnitudeSpectrumGraphWithRoiMask(
                    self.magnitude_spectrum_plot[i], self.params[i]
                )
            )
            self.magnitude_spectrum_graph[i].vmin = self.spectrum_graph_min_db
            self.magnitude_spectrum_graph[i].initialize(color="blue").make_plot()

            # remove axis ticks and titles where redundant
            self.magnitude_spectrum_plot[i].tick_params(labelbottom=False)
            if i != 0:
                self.magnitude_spectrum_plot[i].tick_params(labelleft=False)
                self.magnitude_waterfall_plot[i].tick_params(labelleft=False)
                self.magnitude_waterfall_plot[i].set_ylabel("")

        self.fig_ref.canvas.callbacks.connect("button_press_event", self.click_handler)  # type: ignore

        self.compass_plot = self.fig_ref.add_subplot(
            grid_spec[1, 1], projection="polar"
        )
        self.df_plot = self.fig_ref.add_subplot(grid_spec[0, 1], projection="polar")

        compass_graph_params = GraphParameters()
        self.df_current_graph = CompassGraph(
            self.df_plot, compass_graph_params
        ).initialize("lightseagreen", "DF Angle")
        self.df_graph = (
            CompassGraphWithDeviation(self.df_plot, compass_graph_params)
            .initialize("blue", "DF Mean")
            .make_plot()
        )

        self.compass_df_graph = CompassGraph(
            self.compass_plot, compass_graph_params
        ).initialize("blue", "DF Heading")
        self.compass_graph = (
            CompassGraph(self.compass_plot, compass_graph_params)
            .initialize("red", "UAV Heading", nesw=True)
            .make_plot()
        )

        self.compass_plot.legend(loc="upper left", bbox_to_anchor=(1, 1.1))
        self.df_plot.legend(loc="upper left", bbox_to_anchor=(1, 1))

        self.graph_list = [
            graph
            for graph in self.magnitude_waterfall_graph
            + self.magnitude_spectrum_graph
            + [
                self.df_current_graph,
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

    def update_imag(self, frame_number: int) -> list[matplotlib.artist.Artist]:
        self.update_sensors_and_graphs()
        image_list = []
        for graph in self.graph_list:
            graph.update()
            image_list.extend(graph.collect_images())
        return image_list

    def click_handler(self, event: Any) -> None:
        if (
            self.master.client.source_manager.cs_status
            == CoreServiceStatus.DISCONNECTED
        ):
            return
        if self.magnitude_spectrum_graph is None:
            return
        for magnitude_graph in self.magnitude_spectrum_graph:
            if event.inaxes == magnitude_graph.plot:
                center_frequency = magnitude_graph.coord_to_freq(event.xdata)
                threshold = event.ydata
                self.roi_click_handler_function(center_frequency, threshold)

    def update_roi_graph(
        self, pp_config: proto_cmd.PostProcessingConfig, active_roi: int = -1
    ):
        self._logger.debug(f"Updating ROI graph using:\n{pp_config}")
        for graph in self.magnitude_spectrum_graph:
            graph.update_roi(pp_config.roi, active_roi)

    def highlight_selected_roi(self, active_roi):
        for graph in self.magnitude_spectrum_graph:
            graph.highlight_selected_roi(active_roi)

    def _draw_roi_window(
        self, roi_center: float, roi_width: float, roi_threshold: float
    ) -> None:
        # TODO multi-part roi mask
        for graph, param in zip(self.magnitude_spectrum_graph, self.params):
            graph.roi_center = graph.freq_to_coord(roi_center)
            graph.roi_width = int(roi_width * (param.bin_count / param.iq_rate))
            graph.roi_threshold = roi_threshold

    def update_sensors_and_graphs(self) -> None:
        assert self.df_graph is not None  ##TODO: assert for all or no compass graphs?

        detection: proto_data.Detection | None = self.master.detection_to_plot
        heading: proto_heading.HeadingData | None = self.master.heading_to_plot
        self.df_current_graph.add_point(detection.azimuth if detection else None)
        self.df_graph.add_point(
            detection.mean_azimuth if detection else None,
            detection.deviation if detection else None,
        )

        yaw = None
        if heading is not None:
            if len(heading.quaternion) == 4:
                yaw, _, _ = yaw_pitch_roll_from_quaternion(heading.quaternion)

        self.compass_graph.add_point(yaw)

        df_corrected = calculate_df_corrected(
            df_value=detection.mean_azimuth if detection else None,
            compass_heading=yaw,
        )

        self.compass_df_graph.add_point(df_corrected)

    def plot_spectrum_packet(
        self,
        spectrum,
        signal_db: float = 0.0,
        noise_db: float = 0.0,
        scanning: bool = True,
    ) -> None:
        if self.make_plots == False:
            return

        # Decoding spectrum data
        spectrum_data = protobuf_spectrum_to_numpy(spectrum)
        bin_count = len(spectrum_data)
        center_frequency = spectrum.center_frequency
        iq_rate = spectrum.bandwidth

        if bin_count == 0 or iq_rate == 0:
            return

        is_scanning = (
            self.master.client.source_manager.latest_telemetry is not None
            and self.master.client.source_manager.latest_telemetry.scanengine_state in (
                str(ScanEngineState.SCANNING_IN_PROGRESS).split(".")[-1],
                str(ScanEngineState.SCANNING_IDLE).split(".")[-1],
            )
        )  # TODO: protobuf telemetry shouldn't send SE state in enum instead of string

        spectrum_index = self._check_existing_spectrum_plots(
            bin_count, center_frequency, iq_rate, is_scanning
        )
        if spectrum_index is None:
            new_row = "\n" # cant have '\' inside f-string expressions
            self._logger.warning(
                f"No spectrum found with cf={center_frequency}, iq_rate={iq_rate}, bin_count={bin_count}\n"
                f"List pof spectrum params (len={len(self.params)}): \n"
                f"cf\t\tiq\t\tbc\n"
                f"{new_row.join([f'{p.center_frequency}    {p.iq_rate}   {p.bin_count}' for p in self.params])}"
            )
        else:
            if bin_count != self.params[spectrum_index].bin_count:
                wanted_bc = self.params[spectrum_index].bin_count
                spectrum_data = self.squeeze_spectrum_to_plot(
                    spectrum_data, bin_count, wanted_bc
                )

        if self.redraw_canvas or spectrum_index is None:
            # Animation can be created, because at this point we know bin count and other properties
            # Also restart when bin count or any other parameter has changed

            spectrum_index = self._update_spectrum_plot_list(
                bin_count, center_frequency, iq_rate, is_scanning, spectrum_index
            )

        assert self.magnitude_waterfall_graph is not None
        assert self.magnitude_spectrum_graph is not None
        self.magnitude_waterfall_graph[spectrum_index].add_data(spectrum_data)
        self.magnitude_spectrum_graph[spectrum_index].add_data(spectrum_data)
        self.magnitude_spectrum_graph[spectrum_index].signal_lvl = signal_db
        self.magnitude_spectrum_graph[spectrum_index].noise_lvl = noise_db

    @run_once(timeout=30)
    def _warn_extend(self, extend_count, bin_count, wanted_bc):
        self._logger.warning(
            f"Incoming spectrogram extended with {extend_count} "
            f"zeros from bc={bin_count} so it fits the plots (bc={wanted_bc})"
            f"\nTHE SHOWN SPECTRUM PLOTS MIGHT HAVE MISALIGNED X AXES"
        )

    @run_once(timeout=30)
    def _warn_truncate(self, truncate_count, bin_count, wanted_bc):
        self._logger.warning(
            f"Incoming spectrogram truncated by {truncate_count} "
            f"from bc={bin_count} so it fits the plots (bc={wanted_bc})."
            f"\nTHE SHOWN SPECTRUM PLOTS MIGHT HAVE MISALIGNED X AXES"
        )

    def squeeze_spectrum_to_plot(self, spectrum_data, bin_count, wanted_bc):
        """Either appends or removes a few bins of the spectrum array, so that it matches the length of plot."""

        if bin_count < wanted_bc:
            extend_count = wanted_bc - bin_count  # extending spectrogram
            spectrum_data = np.concatenate(
                [
                    [0] * floor(extend_count / 2),
                    spectrum_data,
                    [0] * ceil(extend_count / 2),
                ]
            )
            self._warn_extend(extend_count, bin_count, wanted_bc)
        if bin_count > wanted_bc:
            truncate_count = bin_count - wanted_bc
            spectrum_data = spectrum_data[
                floor(truncate_count / 2) : -ceil(truncate_count / 2)
            ]
            self._warn_truncate(truncate_count, bin_count, wanted_bc)

        return spectrum_data

    def _update_spectrum_plot_list(
        self, bin_count, center_frequency, iq_rate, is_scanning, spectrum_index
    ):
        """Update self.params and call self.create_anim() as needed"""
        new_graph = GraphParameters()
        new_graph.bin_count = bin_count
        new_graph.iq_rate = iq_rate
        new_graph.center_frequency = center_frequency
        new_graph.waterfall_size = read_from_conf(
            self.conf, ["display", "waterfall_size"], 200
        )
        if is_scanning:
            self.params.append(new_graph)
        else:
            self.params = [new_graph]

        spectrum_index = len(self.params) - 1
        self.create_anim()
        self.redraw_canvas = False
        return spectrum_index

    def _check_existing_spectrum_plots(
        self, bin_count, center_frequency, iq_rate, is_scanning
    ):
        """
        Returns the index of the spectrum plot, if one already exists with the given parameters.
        Also sets self.redraw_canvas if needed.

        Returns None if no existing plot matches the parameters.
        """
        spectrum_index = None
        for i, param in enumerate(self.params):  # finding the graph for the packet
            if (
                abs(center_frequency - param.center_frequency) < 1e-3
                and 0.8 < bin_count / param.bin_count <= 1.2
                and abs(iq_rate - param.iq_rate) < 1e-3
            ):
                spectrum_index = i

        if len(self.params) > 1 and not is_scanning:
            # After exiting scanning mode, redraw even if spectrum plot is found
            self.redraw_canvas = True
        return spectrum_index

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
        self.params = []
        self.redraw_canvas = True

    def disable_plotting(self) -> None:
        self.make_plots = False
        self.magnitude_waterfall_plot = []
        self.magnitude_waterfall_graph = []
        self.magnitude_spectrum_plot = []
        self.magnitude_spectrum_graph = []
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
        for param in self.params:
            param.waterfall_size = waterfall_size

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
    def __init__(
        self,
        master,
        plot_frame,
        send_commands_function: Callable[[str], None],
        conf,
        *args,
        **kwargs,
    ):
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
            read_from_conf(conf, ["display", "spectrum_graph_min_db"], -120),
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
            column=1, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )


        spectrum_selector_label = tkinter.Label(self, text="Spectrum channel:")
        spectrum_selector_label.grid(column=0, row=7, padx=5, pady=8, sticky=tkinter.S)

        self.channel_spectrum_combo = ttk.Combobox(self, width=1)
        self.channel_spectrum_combo["values"] = [0, 1, 2, 3]
        self.channel_spectrum_combo.grid(
            column=1, row=7, padx=5, pady=8, sticky=tkinter.S
        )
        self.channel_spectrum_combo.bind(
            "<<ComboboxSelected>>", self.choose_spectrum_commands
        )
        self.channel_spectrum_combo.configure(state="disabled")

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
            max_bin_count = read_from_conf(
                self.conf, ["display", "max_bin_count"], 1024
            )
            self.max_bin_count_entry.set(max_bin_count)

        waterfall_size = self.waterfall_size_entry.get()
        if waterfall_size <= 0:
            waterfall_size = read_from_conf(
                self.conf, ["display", "waterfall_size"], 200
            )
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
        pass  # TODO: implement using protobuf
        # self.send_commands_function(
        #     f"DEBUG:SpectrumChannel! {self.channel_spectrum_combo.current()};"
        # )
