#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 21/12/2022.
#
from __future__ import annotations

import argparse
import math
import multiprocessing
import threading
import time
import tkinter
from datetime import datetime
from typing import Callable, Optional, Any

import tkinter.messagebox
import matplotlib.cm
import numpy as np
from matplotlib import pyplot
from matplotlib.animation import FuncAnimation  # type: ignore
from matplotlib.backend_bases import KeyEvent, key_press_handler  # type: ignore
from matplotlib.backends.backend_tkagg import (  # type: ignore
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

import pysagax
from pysagax import (
    CompassSensor,
    GraphImage,
    GraphParameters,
    WaterfallAngleGraph,
    ThreeDimensionGraph,
    CompassGraph,
    ThreeDimensionObject,
    CalibrationStatus,
)

parser = argparse.ArgumentParser(description="Compass tester parameters")
parser.add_argument(
    "--wf",
    metavar="N",
    type=int,
    default=1000,
    help="waterfall size (set if experiencing performance issues)",
)
parser.add_argument(
    "--fps",
    metavar="N",
    type=int,
    default=30,
    help="matplotlib display framerate",
)
parser.add_argument(
    "--fs",
    metavar="N",
    type=int,
    default=25,
    help="compass sensor sampling rate",
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
args = parser.parse_args()

compass_data = np.empty([0, 3])

compass = CompassSensor(
    pysagax.AaroniaParser() if args.aaronia else pysagax.SimpleParser(),
)


"""
This thread is responsible for handling the multiprocessing stream process and for displaying the stream contents
on the matplotlib plots
"""


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

        self.three_d_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the 3d plot
        """

        self.three_d_heading: Optional[ThreeDimensionObject] = None
        """
        Matplotlib image object for the heading
        """

        self.three_d_magnetometer: Optional[ThreeDimensionGraph] = None
        """
        Matplotlib image object for the magnetometer sensor
        """

        self.three_d_magneto_heading: Optional[ThreeDimensionGraph] = None
        """
        Matplotlib image object for the magnetometer sensor
        """

        self.three_d_accelerometer: Optional[ThreeDimensionGraph] = None
        """
        Matplotlib image object for the acc sensor
        """

        self.three_d_gyroscope: Optional[ThreeDimensionGraph] = None
        """
        Matplotlib image object for the gyro sensor
        """

        self.waterfall_plot: Optional[object] = None
        """
        Matplotlib plot (axes) object for the waterfall plot
        """

        self.waterfall_magneto: Optional[WaterfallAngleGraph] = None
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

        self.compass_magneto_graph: Optional[CompassGraph] = None
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

    def read_from_compass_sensor(self) -> None:
        global compass
        global compass_data
        global args
        if compass is not None:
            if self.waterfall_compass is not None:
                self.waterfall_compass.add_point(compass.angle)

            if self.compass_graph is not None:
                self.compass_graph.add_point(compass.angle)

            if self.three_d_heading is not None:
                if compass.heading is not None:
                    self.three_d_heading.add_point(compass.quaternion)
                if (
                    compass.parser.magnetometer_values is not None
                    and compass.magnetometer_values is not None
                    and self.three_d_magnetometer is not None
                    and self.compass_magneto_graph is not None
                    and self.three_d_magneto_heading is not None
                    and self.compass_heading_graph is not None
                    and self.waterfall_magneto is not None
                ):
                    from pyquaternion import Quaternion  # type: ignore

                    self.compass_magneto_graph.add_point(
                        -math.atan2(
                            compass.magnetometer_values[1],
                            compass.magnetometer_values[0],
                        )
                    )
                    self.waterfall_magneto.add_point(
                        -math.atan2(
                            compass.magnetometer_values[1],
                            compass.magnetometer_values[0],
                        )
                    )
                    quaternion = Quaternion(compass.quaternion)
                    magneto_rot = quaternion.rotate(compass.magnetometer_values)
                    self.three_d_magneto_heading.add_point(
                        magneto_rot[0] * 10,
                        magneto_rot[1] * 10,
                        magneto_rot[2] * 10,
                    )
                    self.compass_heading_graph.add_point(
                        Quaternion([1, *magneto_rot]).yaw_pitch_roll[0]
                    )
                    self.three_d_magnetometer.add_point(
                        compass.magnetometer_values[0] * 10,
                        compass.magnetometer_values[1] * 10,
                        compass.magnetometer_values[2] * 10,
                    )
                if (
                    compass.gyroscope_values is not None
                    and self.three_d_gyroscope is not None
                ):
                    self.three_d_gyroscope.add_point(
                        compass.gyroscope_values[0],
                        compass.gyroscope_values[1],
                        compass.gyroscope_values[2],
                    )
                if (
                    compass.accelerometer_values is not None
                    and self.three_d_accelerometer is not None
                ):
                    self.three_d_accelerometer.add_point(
                        compass.accelerometer_values[0],
                        compass.accelerometer_values[1],
                        compass.accelerometer_values[2],
                    )
            compass_data = np.append(  # for octave export
                compass_data,
                np.array(
                    [compass.heading if compass is not None else ["NaN", "NaN", "NaN"]]
                ),
                axis=0,
            )
            time.sleep(1 / float(args.fs))

    def run(self) -> None:
        """
        Entry point of the data handling thread
        """

        global args

        # The code below will handle the preprocessed packets from the stream process
        assert self.status_label_ref
        self.create_anim()
        self.animation_started = True
        while True:
            if self.disconnect:
                break
            self.read_from_compass_sensor()

        self.animation_started = False

    def update_imag(self, frame_number: int) -> list[matplotlib.artist.Artist]:
        image_list = []
        for graph in self.graph_list:
            graph.update()
            image_list.extend(graph.collect_images())

        calibrations = {
            "Magneto": compass.magnetometer_calibration,
            "Gyro": compass.gyroscope_calibration,
            "Accel": compass.accelerometer_calibration,
        }
        status_text = []
        for label, calibration in calibrations.items():
            if calibration.status in [
                CalibrationStatus.CALIBRATING,
                CalibrationStatus.ACTION_REQUIRED,
            ]:
                status_text = [f"{label}: {calibration}"]
                break
            else:
                status_text.append(f"{label}: {calibration}")
        if self.status_label_ref:
            self.status_label_ref.config(text=", ".join(status_text))
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
            nrows=2, ncols=2, width_ratios=(3, 2), height_ratios=(1, 1)
        )
        self.three_d_plot = self.fig_ref.add_subplot(grid_spec[:, 0], projection="3d")
        self.waterfall_plot = self.fig_ref.add_subplot(grid_spec[0, 1])
        self.compass_plot = self.fig_ref.add_subplot(
            grid_spec[1, 1], projection="polar"
        )
        if compass is not None:
            self.waterfall_magneto = WaterfallAngleGraph(
                self.waterfall_plot, self.params
            ).initialize("blue", "Magnetometer Heading")
            self.waterfall_compass = (
                WaterfallAngleGraph(self.waterfall_plot, self.params)
                .initialize("red", "AHRS Heading")
                .make_plot()
            )
            self.waterfall_compass.plot.set_ylabel("")
            self.waterfall_compass.plot.yaxis.set_major_formatter(  # type: ignore
                lambda x, y: f"{float(x - self.params.waterfall_size)/float(args.fs):.2f}s"
            )
            self.three_d_heading = ThreeDimensionObject(
                self.three_d_plot, self.params
            ).initialize("red", "Heading")
            self.three_d_magnetometer = ThreeDimensionGraph(
                self.three_d_plot, self.params
            ).initialize("blue", "Magnetometer [nT*10]")
            self.three_d_magneto_heading = ThreeDimensionGraph(
                self.three_d_plot, self.params
            ).initialize("purple", "Magnetometer direction", vector_disp=True)
            self.three_d_accelerometer = ThreeDimensionGraph(
                self.three_d_plot, self.params
            ).initialize("green", "Accelerometer [m/s²]")
            self.three_d_gyroscope = (
                ThreeDimensionGraph(self.three_d_plot, self.params)
                .initialize("yellow", "Gyroscope [rad/s]")
                .make_plot()
            )
            self.three_d_gyroscope.image.set_visible(False)  # type: ignore
            self.three_d_accelerometer.image.set_visible(False)  # type: ignore
            self.three_d_magneto_heading.image.set_visible(False)  # type: ignore
            self.compass_graph = CompassGraph(
                self.compass_plot, self.params
            ).initialize("red", "AHRS Heading")
            self.compass_magneto_graph = CompassGraph(
                self.compass_plot, self.params
            ).initialize("blue", "Magnetometer Heading")
            self.compass_heading_graph = (
                CompassGraph(self.compass_plot, self.params)
                .initialize("purple", "Magnetometer Reference")
                .make_plot()
            )

        self.graph_list = [
            graph
            for graph in [
                self.waterfall_compass,
                self.waterfall_magneto,
                self.three_d_heading,
                self.three_d_magnetometer,
                self.three_d_magneto_heading,
                self.three_d_accelerometer,
                self.three_d_gyroscope,
                self.compass_graph,
                self.compass_heading_graph,
                self.compass_magneto_graph,
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

        self.display_thread: Optional[DisplayThread] = None

        self.fig: Optional[pyplot.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.canvas_toolbar: Optional[NavigationToolbar2Tk] = None

        self.pack(fill=tkinter.BOTH, expand=1)

        status_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        status_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)
        self.status_label = tkinter.Label(
            status_frame, text="", font=tkinter.font.Font(size=10)
        )
        self.status_label.pack(side=tkinter.TOP, padx=5, pady=10, anchor="w")
        buttons_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        buttons_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        self.save_octave_button = tkinter.Button(
            buttons_frame, text="Save Octave", command=self.save_octave_commands
        )
        self.save_octave_button.pack(side=tkinter.RIGHT)

        self.reset_ahrs_button = tkinter.Button(
            buttons_frame, text="Reset AHRS", command=self.reset_ahrs_commands
        )
        self.reset_ahrs_button.pack(side=tkinter.RIGHT)

        self.calibrate_gyro_button = tkinter.Button(
            buttons_frame, text="Calibrate Gyro", command=self.gyro_calibration_commands
        )
        self.calibrate_gyro_button.pack(side=tkinter.RIGHT)

        self.calibrate_acc_button = tkinter.Button(
            buttons_frame, text="Calibrate Acc", command=self.acc_calibration_commands
        )
        self.calibrate_acc_button.pack(side=tkinter.RIGHT)

        self.calibrate_magneto_button = tkinter.Button(
            buttons_frame,
            text="Calibrate Magneto",
            command=self.magneto_calibration_commands,
        )
        self.calibrate_magneto_button.pack(side=tkinter.RIGHT)

        self.load_calibration_button = tkinter.Button(
            buttons_frame,
            text="Load Calibration",
            command=self.load_calibration_commands,
        )
        self.load_calibration_button.pack(side=tkinter.RIGHT)

        self.save_calibration_button = tkinter.Button(
            buttons_frame,
            text="Save Calibration",
            command=self.save_calibration_commands,
        )
        self.save_calibration_button.pack(side=tkinter.RIGHT)

        beta_scale_label = tkinter.Label(
            buttons_frame, text="Filter beta: ", font=tkinter.font.Font(size=10)
        )
        beta_scale_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")
        self.beta_scale = tkinter.Scale(
            buttons_frame,
            command=self.set_beta_commands,
            from_=0,
            to=0.5,
            resolution=0.002,
            length=200,
            orient=tkinter.HORIZONTAL,
        )
        self.beta_scale.pack(side=tkinter.LEFT)

        self.plot_frame = tkinter.Frame(self)
        self.create_canvas()
        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        global compass
        compass.set_serial_device(
            pysagax.open_aaronia_serial_dev()
            if args.aaronia
            else pysagax.open_arduino_serial_dev(args.sensor_dev)
        )
        compass.start()

        self.status_label.config(text="Connected")

        self.connect_commands()

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
        if self.display_thread is not None:
            self.display_thread.fig_ref = self.fig

    def connect_commands(self) -> None:
        """
        Action of the "Connect" button
        """
        self.display_thread = DisplayThread()
        self.display_thread.recreate_canvas_action = self.create_canvas
        self.display_thread.status_label_ref = self.status_label
        self.display_thread.start()

    def save_octave_commands(self) -> None:
        """
        Action of the "Connect" button
        """
        global compass_data
        pysagax.save_octave(
            filename=f"octave{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            variables={"compass": compass_data},
        )

        compass_data = np.empty([0, 3])

    def gyro_calibration_commands(self) -> None:
        if self.calibrate_gyro_button.config("relief")[-1] == "sunken":
            self.calibrate_gyro_button.config(relief="raised")
            compass.gyroscope_calibration.end_calibration()
            self.beta_scale.set(compass.gyroscope_calibration.gyro_beta)
        else:
            self.calibrate_gyro_button.config(relief="sunken")
            compass.gyroscope_calibration.begin_calibration()

    def acc_calibration_commands(self) -> None:
        compass.accelerometer_calibration.next_calibration_step()

    def magneto_calibration_commands(self) -> None:
        if self.calibrate_magneto_button.config("relief")[-1] == "sunken":
            self.calibrate_magneto_button.config(relief="raised")
            compass.magnetometer_calibration.end_calibration()
        else:
            self.calibrate_magneto_button.config(relief="sunken")
            compass.magnetometer_calibration.begin_calibration()

    def reset_ahrs_commands(self) -> None:
        compass.reset_ahrs_filter()

    def save_calibration_commands(self) -> None:
        compass.save_calibration()
        tkinter.messagebox.showinfo(
            title="Saved", message="Calibration saved to calibration.npz"
        )

    def load_calibration_commands(self) -> None:
        compass.load_calibration()
        self.beta_scale.set(compass.gyroscope_calibration.gyro_beta)
        tkinter.messagebox.showinfo(
            title="Loaded", message="Loaded calibration from calibration.npz"
        )

    def set_beta_commands(self, args: Any) -> None:
        compass.gyroscope_calibration.gyro_beta = self.beta_scale.get()

    def disconnect_commands(self) -> None:
        """
        Action of the "Disconnect" button
        """
        if self.display_thread is not None:
            self.display_thread.disconnect = True


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = ClientWindow()
    root.geometry("1024x768")
    root.wm_title("Sagax Compass Tester")
    root.mainloop()
    ex.disconnect_commands()
