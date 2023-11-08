#
# Created by aron.szabo@sagaxcommunications.com on 15/05/2022.
#
from typing import Any, Optional

import pyquaternion
import matplotlib
import numpy
import numpy as np
import numpy.typing as npt
from matplotlib import cm
from matplotlib.animation import FuncAnimation  # type: ignore
from matplotlib.backends.backend_tkagg import (  # type: ignore
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # type: ignore


class GraphParameters:
    def __init__(self) -> None:
        self.iq_rate: float = 0
        """
        IQ rate of the last burst
        """

        self.center_frequency: float = 0
        """
        IQ rate of the last burst
        """

        self.bin_count: int = 0
        """
        Bin count of the last burst
        """

        self.waterfall_size: int = 0
        """
        Amount of spectrum lines to be displayed on the waterfall diagram.
        """


class GraphImage:
    def __init__(self, plot: matplotlib.axes.SubplotBase) -> None:
        self.plot: matplotlib.axes.SubplotBase = plot
        """
        Matplotlib plot (axes) object for the plot
        """

        self.image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object
        """

        self.marker_image: Optional[matplotlib.artist.Artist] = None
        """
        Matplotlib image object
        """

    def init_plot(self) -> None:
        pass

    def init_image(self) -> None:
        pass

    def update(self) -> None:
        pass

    def add_data(self, data: npt.NDArray[np.float64]) -> None:
        pass

    def collect_images(self) -> list[matplotlib.artist.Artist]:
        image_list = []
        if self.image is not None:
            image_list.append(self.image)
        if self.marker_image is not None:
            image_list.append(self.marker_image)
        return image_list


pi_chr = chr(0x03C0)


class HalfLocator(matplotlib.ticker.Locator):  # type: ignore
    """
    Tick locator for matplotlib plot
    Set a tick on each integer multiple of a base within the view interval.
    """

    def __init__(self, min: float = 0, max: float = 1.0) -> None:
        self._min = min
        self._max = max

    def set_params(self, min: float, max: float) -> None:
        """Set parameters within this locator."""
        if min is not None:
            self._min = min
        if max is not None:
            self._max = max

    def __call__(self) -> list[float]:
        """Return the locations of the ticks."""
        vmin, vmax = self.axis.get_view_interval()
        return self.tick_values(vmin, vmax)

    def tick_values(self, vmin: float, vmax: float) -> list[float]:
        if vmax < vmin:
            vmin, vmax = vmax, vmin

        step = (self._max - self._min) / 4
        locs: list[float] = []
        while len(locs) < 4:
            locs = [
                loc
                for loc in np.arange(self._min, self._max, step)
                if vmin <= loc <= vmax
            ]
            step /= 2
        if self._max <= vmax:
            locs.append(self._max)
        return self.raise_if_exceeds(locs)  # type: ignore

    def view_limits(self, dmin: float, dmax: float) -> tuple[float, float]:
        """
        Set the view limits
        """
        return matplotlib.transforms.nonsingular(dmin, dmax, expander=1e-12, tiny=1e-13)  # type: ignore


class WaterfallMagnitudeGraph(GraphImage):
    def __init__(
        self, plot: matplotlib.axes.SubplotBase, params: GraphParameters
    ) -> None:
        super().__init__(plot)
        self.params = params
        self.waterfall = np.ones([self.params.waterfall_size, self.params.bin_count])
        """
        Magnitude waterfall data (numpy matrix)
        """
        self.decimated_waterfall = np.ones(
            [self.params.waterfall_size, self.params.bin_count]
        )

        self.vmin: float = -120
        self.vmax: float = 0

        self.decimate = 1
        self.new_lim = (0, self.params.bin_count)
        self.max_points = 1024

    def ax_update(self, event_ax: Any) -> None:
        if event_ax is None:
            xlims = (0, self.params.bin_count)
        else:
            xlims = event_ax.get_xlim()
        self.new_lim = int(max(0, xlims[0])), int(min(self.params.bin_count, xlims[1]))
        self.decimate = (self.new_lim[1] - self.new_lim[0]) // self.max_points
        if self.decimate < 1:
            self.decimate = 1
        # self.decimated_waterfall = self.waterfall[:, self.new_lim[0]:self.new_lim[1]:self.decimate]
        self.decimated_waterfall = self.waterfall[:, :: self.decimate]

    def bin_freq_formatter(self, x: float, pos: Any = None) -> str:
        return f"{((x - self.params.bin_count / 2) * (self.params.iq_rate / self.params.bin_count) + self.params.center_frequency) / 1e6:.3f}M"

    def sample_id_formatter(self, x: float, pos: Any = None) -> str:
        return f"{-x:.0f}"

    def magnitude_format_coord(self, x: float, y: float) -> str:
        return f"Frequency: {self.bin_freq_formatter(x)} (bin {int(x)}), Packet: {self.sample_id_formatter(y)}"

    def initialize(self) -> "WaterfallMagnitudeGraph":
        self.init_image()
        return self

    def make_plot(self) -> "WaterfallMagnitudeGraph":
        self.init_plot()
        return self

    def init_image(self) -> None:
        super().init_image()
        assert self.plot is not None
        self.waterfall = np.zeros([self.params.waterfall_size, self.params.bin_count])
        self.image = self.plot.imshow(
            self.waterfall,
            cmap=matplotlib.cm.get_cmap("gnuplot"),  # type: ignore
            animated=True,
            vmax=self.vmax,
            vmin=self.vmin,
        )

    def init_plot(self) -> None:
        super().init_plot()
        assert self.plot is not None
        self.plot.xaxis.set_major_formatter(  # type: ignore
            matplotlib.ticker.FuncFormatter(self.bin_freq_formatter)  # type: ignore
        )
        self.plot.xaxis.set_major_locator(HalfLocator(max=self.params.bin_count))  # type: ignore
        self.plot.tick_params(axis="x", labelrotation=45)  # type: ignore
        self.plot.yaxis.set_major_formatter(  # type: ignore
            matplotlib.ticker.FuncFormatter(self.sample_id_formatter)  # type: ignore
        )
        self.plot.format_coord = self.magnitude_format_coord  # type: ignore
        self.plot.set_label("Magnitude")  # type: ignore
        self.plot.set_ylabel("Packets")
        self.plot.set_aspect("auto")  # type: ignore
        self.plot.callbacks.connect("xlim_changed", self.ax_update)  # type:ignore
        # self.plot.callbacks.connect("ylim_changed", self.ax_update)
        self.ax_update(None)

    def update(self) -> None:
        super().update()
        self.image.set_data(self.decimated_waterfall)  # type: ignore

    def add_data(self, data: npt.NDArray[np.float64]) -> None:
        super().add_data(data)
        self.waterfall = np.append(
            np.array([data]),
            self.waterfall[:-1, :],
            axis=0,
        )
        try:
            self.decimated_waterfall = np.append(
                np.array([data[:: self.decimate]]),
                self.decimated_waterfall[:-1, :],
                axis=0,
            )
        except ValueError:
            self.decimated_waterfall = self.waterfall[:, :: self.decimate]


class AngleSpectrumGraph(GraphImage):
    def __init__(
        self, plot: matplotlib.axes.SubplotBase, params: GraphParameters
    ) -> None:
        super().__init__(plot)
        self.params = params

        self.spectrum = np.zeros([self.params.bin_count])
        """
        Spectrum data (numpy vector)
        """
        self.marker_enabled: bool = False
        """
        Marker display is enabled
        """

        self.marker_bin: int = 0
        """
        Location of the marker
        """

        self.marker_value: float = 0
        """
        Value of marker
        """

        self.color: str = "blue"
        """
        Color of the plot image
        """

    def bin_freq_formatter(self, x: float, pos: Any = None) -> str:
        return f"{((x - self.params.bin_count / 2) * (self.params.iq_rate / self.params.bin_count) + self.params.center_frequency) / 1e6:.3f}M"

    def angle_format_coord(self, x: float, y: float) -> str:
        if 0 < x < len(self.spectrum):
            val = self.spectrum[int(x)]
        else:
            val = numpy.float64(0.0)
        return (
            f"Frequency: {self.bin_freq_formatter(x)} (bin {int(x)}), "
            f"Angle: {val:.3f} rad ({val / np.pi * 180:.2f} deg)"
        )

    def init_image(self) -> None:
        super().init_image()
        self.spectrum = np.zeros([self.params.bin_count])
        self.image = self.plot.plot(  # type: ignore
            self.spectrum, lw=1, color=self.color, animated=True
        )[0]
        self.marker_image = self.plot.plot(0, 0, "or", animated=True)[0]  # type: ignore

    def initialize(self, color: str) -> "AngleSpectrumGraph":
        self.color = color
        self.init_image()
        return self

    def make_plot(self) -> "AngleSpectrumGraph":
        self.init_plot()
        return self

    def init_plot(self) -> None:
        super().init_plot()
        assert self.plot is not None
        self.plot.xaxis.set_major_formatter(  # type: ignore
            matplotlib.ticker.FuncFormatter(self.bin_freq_formatter)  # type: ignore
        )

        self.plot.xaxis.set_major_locator(HalfLocator(max=self.params.bin_count))  # type: ignore
        self.plot.tick_params(axis="x", labelrotation=45)  # type: ignore
        self.plot.yaxis.set_major_formatter(  # type: ignore
            matplotlib.ticker.StrMethodFormatter("{x:.2f}")  # type: ignore
        )
        self.plot.grid(axis="both")
        self.plot.format_coord = self.angle_format_coord  # type: ignore
        self.plot.set_ylim(-np.pi, np.pi)
        self.plot.set_yticks([-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi])
        self.plot.set_yticklabels(
            [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
        )
        self.plot.set_aspect("auto")  # type: ignore

    def update(self) -> None:
        super().update()
        self.image.set_ydata(self.spectrum)  # type: ignore
        self.marker_image.set_xdata(self.marker_bin)  # type: ignore
        self.marker_image.set_ydata(self.marker_value)  # type: ignore

    def add_data(self, data: npt.NDArray[np.float64]) -> None:
        super().add_data(data)
        self.set_data(data)

    def set_data(self, data: npt.NDArray[np.float64]) -> None:
        self.spectrum = data


class MagnitudeSpectrumGraph(GraphImage):
    def __init__(
        self, plot: matplotlib.axes.SubplotBase, params: GraphParameters
    ) -> None:
        super().__init__(plot)
        self.params = params

        self.spectrum = np.zeros([self.params.bin_count])
        """
        Spectrum data (numpy vector)
        """
        self.marker_enabled: bool = False
        """
        Marker display is enabled
        """

        self.marker_bin: int = 0
        """
        Location of the marker
        """

        self.marker_value: float = 0
        """
        Value of marker
        """

        self.color: str = "blue"
        """
        Color of the plot image
        """
        self.vmin: float = -120
        self.vmax: float = 0
        self.rect: Any = None
        self.roi_center = 0
        self.roi_width = 0
        self.roi_threshold = 0

    def coord_to_freq(self, coord: float) -> float:
        return (coord - self.params.bin_count / 2) * (
            self.params.iq_rate / self.params.bin_count
        ) + self.params.center_frequency

    def bin_freq_formatter(self, x: float, pos: Any = None) -> str:
        return f"{self.coord_to_freq(x) / 1e6:.3f}M"

    def angle_format_coord(self, x: float, y: float) -> str:
        if 0 < x < len(self.spectrum):
            val = self.spectrum[int(x)]
        else:
            val = numpy.float64(0.0)
        return (
            f"Frequency: {self.bin_freq_formatter(x)} (bin {int(x)}), "
            f"Value: {val:.3f} "
        )

    def init_image(self) -> None:
        super().init_image()
        self.spectrum = np.zeros([self.params.bin_count])
        self.image = self.plot.plot(  # type: ignore
            self.spectrum, lw=1, color=self.color, animated=True
        )[0]
        # Create a Rectangle patch
        self.rect = matplotlib.patches.Rectangle(
            (0, self.vmin),
            0,
            self.vmax - self.vmin,
            linewidth=1,
            edgecolor="r",
            facecolor="none",
        )  # type:ignore

        # Add the patch to the Axes
        self.plot.add_patch(self.rect)  # type:ignore
        self.marker_image = self.plot.plot(0, 0, "or", animated=True)[0]  # type: ignore

    def initialize(self, color: str) -> "MagnitudeSpectrumGraph":
        self.color = color
        self.init_image()
        return self

    def make_plot(self) -> "MagnitudeSpectrumGraph":
        self.init_plot()
        return self

    def init_plot(self) -> None:
        super().init_plot()
        assert self.plot is not None
        self.plot.xaxis.set_major_formatter(  # type: ignore
            matplotlib.ticker.FuncFormatter(self.bin_freq_formatter)  # type: ignore
        )

        self.plot.xaxis.set_major_locator(HalfLocator(max=self.params.bin_count))  # type: ignore
        self.plot.tick_params(axis="x", labelrotation=45)  # type: ignore
        self.plot.yaxis.set_major_formatter(  # type: ignore
            matplotlib.ticker.StrMethodFormatter("{x:.2f}")  # type: ignore
        )
        self.plot.grid(axis="both")
        self.plot.set_ylim(self.vmin, self.vmax)
        self.plot.set_aspect("auto")  # type: ignore

    def update(self) -> None:
        super().update()
        self.image.set_ydata(self.spectrum)  # type: ignore
        self.rect.set_x(self.roi_center - self.roi_width // 2)
        self.rect.set_y(self.roi_threshold)
        self.rect.set_width(self.roi_width)
        # self.rect.set_height( -self.roi_threshold)
        self.marker_image.set_xdata(self.marker_bin)  # type: ignore
        self.marker_image.set_ydata(self.marker_value)  # type: ignore

    def add_data(self, data: npt.NDArray[np.float64]) -> None:
        super().add_data(data)
        self.set_data(data)

    def set_data(self, data: npt.NDArray[np.float64]) -> None:
        self.spectrum = data

    def collect_images(self) -> list[matplotlib.artist.Artist]:
        assert self.image is not None
        return [self.image, self.rect]


class WaterfallAngleGraph(GraphImage):
    def __init__(
        self, plot: matplotlib.axes.SubplotBase, params: GraphParameters
    ) -> None:
        super().__init__(plot)

        self.params = params
        self.waterfall = np.empty([self.params.waterfall_size])
        self.waterfall.fill(None)
        """
        Wf data (numpy vector)
        """
        self.color: str = "blue"
        """
        Color of the plot image
        """
        self.label: str = ""
        """
        Label of the plot image
        """
        self.plot_label: str = ""
        """
        Label of the plot
        """
        self.rad: bool = False
        """
        Display angles in radians
        """

    def sample_id_formatter(self, x: float, pos: Any = None) -> str:
        return f"{x - self.params.waterfall_size:.0f}"

    def roi_format_coord(self, x: float, y: float) -> str:
        return (
            f"Packet: {self.sample_id_formatter(y)}, "
            f"Angle: {x:.3f} rad ({x / np.pi * 180:.2f} deg)"
        )

    def init_image(self) -> None:
        super().init_image()
        assert self.plot is not None
        self.image = self.plot.plot(  # type: ignore
            self.waterfall,
            np.arange(0, self.params.waterfall_size),
            lw=1,
            color=self.color,
            animated=True,
            label=self.label,
        )[0]

    def initialize(
        self, color: str, label: str, rad: bool = True
    ) -> "WaterfallAngleGraph":
        self.color = color
        self.label = label
        self.rad = rad
        self.init_image()
        return self

    def make_plot(self) -> "WaterfallAngleGraph":
        self.init_plot()
        return self

    def init_plot(self) -> None:
        super().init_plot()

        self.plot.yaxis.set_major_formatter(  # type: ignore
            matplotlib.ticker.FuncFormatter(self.sample_id_formatter)  # type: ignore
        )
        self.plot.set_ylabel("Packets")
        self.plot.set_aspect("auto")  # type: ignore

        if self.rad:
            self.plot.xaxis.set_major_formatter(lambda x, y: f"{x/np.pi:.2f}{pi_chr}")  # type: ignore
        else:
            self.plot.xaxis.set_major_formatter(lambda x, y: f"{x/np.pi*180:.2f}°")  # type: ignore

        self.plot.grid(axis="both")

        self.plot.set_xlim(-np.pi, np.pi)
        self.plot.xaxis.set_major_locator(HalfLocator(min=-np.pi, max=np.pi))  # type: ignore
        # self.plot.set_xticks(
        #    [-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi]
        # )
        # self.plot.set_xticklabels(
        #    [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
        # )
        self.plot.format_coord = self.roi_format_coord  # type: ignore
        self.plot.set_label(self.plot_label)  # type: ignore
        self.plot.set_aspect("auto")  # type: ignore
        self.plot.invert_yaxis()  # type: ignore
        self.plot.set_ylim(self.params.waterfall_size, 0)
        self.plot.yaxis.set_label_position("right")  # type: ignore
        self.plot.yaxis.tick_right()  # type: ignore
        self.plot.legend()

    def update(self) -> None:
        super().update()
        self.image.set_xdata(self.waterfall)  # type: ignore

    def add_data(self, data: npt.NDArray[np.float64]) -> None:
        super().add_data(data)

    def add_point(self, point: Optional[float]) -> None:
        self.waterfall = np.append(
            self.waterfall[-self.params.waterfall_size + 1 :],
            np.array([point]),
            axis=0,
        )


class ThreeDimensionGraph(GraphImage):
    def __init__(
        self, plot: matplotlib.axes.SubplotBase, params: GraphParameters
    ) -> None:
        super().__init__(plot)

        self.params = params
        self.waterfall = np.empty([self.params.waterfall_size, 3])
        self.waterfall.fill(None)
        """
        Wf data (numpy vector)
        """
        self.color: str = "blue"
        """
        Color of the plot image
        """
        self.label: str = ""
        """
        Label of the plot image
        """
        self.plot_label: str = ""
        """
        Label of the plot
        """
        self.vector_disp: bool = False

    def init_image(self) -> None:
        super().init_image()
        assert self.plot is not None
        self.image = self.plot.plot(  # type: ignore
            xs=self.waterfall[:, 0],
            ys=self.waterfall[:, 1],
            zs=self.waterfall[:, 2],
            color=self.color,
            animated=True,
            label=self.label,
        )[0]

        self.marker_image = self.plot.plot(  # type: ignore
            0,
            0,
            "" if self.vector_disp else "o",
            color=self.color,
            animated=True,
            markerfacecolor=self.color,
            markeredgecolor="red",
        )[0]

    def initialize(
        self, color: str, label: str, vector_disp: bool = False
    ) -> "ThreeDimensionGraph":
        self.label = label
        self.color = color
        self.vector_disp = vector_disp
        self.init_image()
        return self

    def make_plot(self) -> "ThreeDimensionGraph":
        self.init_plot()
        return self

    def init_plot(self) -> None:
        super().init_plot()

        # self.plot.yaxis.set_major_formatter(  # type: ignore
        #     matplotlib.ticker.FuncFormatter(self.sample_id_formatter)  # type: ignore
        # )
        # self.plot.set_ylabel("Packets")
        # self.plot.set_aspect("auto")  # type: ignore
        #
        # self.plot.xaxis.set_major_formatter(lambda x, y: f"{x/np.pi:.2f}{pi_chr}")  # type: ignore
        # self.plot.grid(axis="both")
        #
        self.plot.set_xlim(-4, 4)
        self.plot.set_ylim(-4, 4)
        self.plot.set_zlim(-4, 4)  # type: ignore
        self.plot.set_xlabel("x")
        self.plot.set_ylabel("y")
        self.plot.set_zlabel("z")  # type: ignore
        # self.plot.xaxis.set_major_locator(HalfLocator(min=-np.pi, max=np.pi))  # type: ignore
        # # self.plot.set_xticks(
        # #    [-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi]
        # # )
        # # self.plot.set_xticklabels(
        # #    [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
        # # )
        # self.plot.format_coord = self.roi_format_coord  # type: ignore
        # self.plot.set_label(self.plot_label)  # type: ignore
        # self.plot.set_aspect("auto")  # type: ignore
        # self.plot.invert_yaxis()  # type: ignore
        # self.plot.set_ylim(self.params.waterfall_size, 0)
        # self.plot.yaxis.set_label_position("right")  # type: ignore
        # self.plot.yaxis.tick_right()  # type: ignore
        self.plot.legend()

    def update(self) -> None:
        super().update()
        self.image.set_xdata(self.waterfall[:, 0])  # type: ignore
        self.image.set_ydata(self.waterfall[:, 1])  # type: ignore
        self.image.set_3d_properties(self.waterfall[:, 2])  # type: ignore

        self.marker_image.set_xdata([0, self.waterfall[-1, 0]] if self.vector_disp else self.waterfall[-1, 0])  # type: ignore
        self.marker_image.set_ydata([0, self.waterfall[-1, 1]] if self.vector_disp else self.waterfall[-1, 1])  # type: ignore
        self.marker_image.set_3d_properties([0, self.waterfall[-1, 2]] if self.vector_disp else self.waterfall[-1, 2])  # type: ignore

    def add_data(self, data: npt.NDArray[np.float64]) -> None:
        super().add_data(data)

    def add_point(
        self, x: Optional[float], y: Optional[float], z: Optional[float]
    ) -> None:
        self.waterfall = np.append(
            self.waterfall[-self.params.waterfall_size + 1 :, :],
            np.array([[x, y, z]]),
            axis=0,
        )


class CompassGraph(GraphImage):
    def __init__(
        self, plot: matplotlib.axes.SubplotBase, params: GraphParameters
    ) -> None:
        super().__init__(plot)

        self.params = params
        self.angle: float = 0
        """
        Compass angle
        """
        self.radius: float = 1
        self.color: str = "blue"
        """
        Color of the plot image
        """
        self.label: str = ""
        """
        Label of the plot image
        """
        self.plot_label: str = ""
        """
        Label of the plot
        """
        self.nesw = False
        """
        Display compass labels
        """

    def sample_id_formatter(self, x: float, pos: Any = None) -> str:
        return f"{x - self.params.waterfall_size:.0f}"

    def roi_format_coord(self, x: float, y: float) -> str:
        return (
            f"Packet: {self.sample_id_formatter(y)}, "
            f"Angle: {x:.3f} rad ({x / np.pi * 180:.2f} deg)"
        )

    def init_image(self) -> None:
        super().init_image()
        assert self.plot is not None
        self.image = self.plot.plot(  # type: ignore
            [0, self.angle],
            [0, self.radius],
            color=self.color,
            animated=True,
            label=self.label,
        )[0]

    def initialize(self, color: str, label: str, nesw: bool = False) -> "CompassGraph":
        self.label = label
        self.color = color
        self.nesw = nesw
        self.init_image()
        return self

    def make_plot(self) -> "CompassGraph":
        self.init_plot()
        return self

    def init_plot(self) -> None:
        super().init_plot()
        self.plot.set_theta_direction(-1)  # type: ignore
        self.plot.set_theta_offset(np.pi / 2.0)  # type: ignore
        if self.nesw:
            self.plot.set_thetagrids(range(0, 360, 45), ("N", "NE", "E", "SE", "S", "SW", "W", "NW"))  # type: ignore
        self.plot.set_rmax(1)  # type: ignore
        self.plot.set_rticks([])  # type: ignore
        self.plot.legend()
        self.plot.grid(True)

    def update(self) -> None:
        super().update()
        self.image.set_xdata([0, self.angle])  # type: ignore
        self.image.set_ydata([0, self.radius])  # type: ignore

    def add_data(self, data: npt.NDArray[np.float64]) -> None:
        super().add_data(data)

    def add_point(self, value: Optional[float]) -> None:
        if value is None:
            self.image.set_visible(False)  # type: ignore
        else:
            self.angle = value
            self.image.set_visible(True)  # type: ignore


class CompassGraphWithDeviation(CompassGraph):
        def __init__(
                self, plot: matplotlib.axes.SubplotBase, params: GraphParameters
        ) -> None:
                super().__init__(plot, params)
                self.deviation: float = 0

        def init_image(self) -> None:
                super().init_image()
                assert self.plot is not None
                self.image = self.plot.plot(  # type: ignore
                        [0, self.angle],
                        [0, self.radius],
                        color=self.color,
                        animated=True,
                )[0]
                
                self.marker_image = self.plot.fill_between(  # type: ignore
                        np.linspace(self.angle-self.deviation, self.angle+self.deviation, 5),
                        0,
                        self.radius,
                        color=self.color,
                        alpha=0.2,
                        animated=True,
                        label=f"{self.label} deviation",
                )
        def update(self) -> None:
                super().update()        #plot the angle
                if self.deviation is not None and self.angle is not None:
                        start = self.angle-self.deviation
                        stop = self.angle+self.deviation
                        count = int((stop - start) / 0.16)+1 # 1 point every ~10°
                        self.marker_image = self.plot.fill_between(  # type: ignore
                                np.linspace(start, stop, count),
                                0,
                                self.radius,
                                color=self.color,
                                alpha=0.2,
                                animated=True,
                                label=f"{self.label} deviation",
                        ) #plot the deviation

        def add_point(self, value: Optional[float], deviation: Optional[float]) -> None:
                if value is None or deviation is None:
                        self.image.set_visible(False)  # type: ignore
                        self.marker_image.set_visible(False)  # type: ignore
                else:
                        self.image.set_visible(True)  # type: ignore
                        self.marker_image.set_visible(True)  # type: ignore
                self.angle = value
                self.deviation = deviation


class ThreeDimensionObject(GraphImage):
    def __init__(
        self, plot: matplotlib.axes.SubplotBase, params: GraphParameters
    ) -> None:
        super().__init__(plot)

        self.params = params
        self.quaternion = pyquaternion.Quaternion(1.0, 0.0, 0.0, 0.0)

        """
        Wf data (numpy vector)
        """
        self.color: str = "blue"
        """
        Color of the plot image
        """
        self.label: str = ""
        """
        Label of the plot image
        """
        self.plot_label: str = ""
        """
        Label of the plot
        """
        face_x = [0.5, 0.5, 0.3, -0.3, -0.5, -0.5]
        face_y = [-1, 0.7, 1, 1, 0.7, -1]
        d = 0.3
        top_scale = 0.8
        self.verts = [
            list(
                zip(
                    [x * top_scale for x in face_x],
                    [y * top_scale for y in face_y],
                    np.repeat(d, len(face_x)),
                )
            ),
            list(zip(face_x, face_y, np.repeat(-d, len(face_x)))),
            *[
                [
                    [x1, y1, -d],
                    [x1 * top_scale, y1 * top_scale, d],
                    [x2 * top_scale, y2 * top_scale, d],
                    [x2, y2, -d],
                ]
                for x1, y1, x2, y2 in zip(
                    face_x[1:], face_y[1:], face_x[:-1], face_y[:-1]
                )
            ],
        ]
        self.poly: Optional[Poly3DCollection] = None

    def init_image(self) -> None:
        super().init_image()
        assert self.plot is not None

        self.poly = Poly3DCollection(verts=self.verts)
        self.poly.set_edgecolor("blue")
        self.poly.set_facecolor(self.color)
        self.image = self.plot.add_collection3d(self.poly)  # type: ignore

    def initialize(self, color: str, label: str) -> "ThreeDimensionObject":
        self.label = label
        self.color = color
        self.init_image()
        return self

    def make_plot(self) -> "ThreeDimensionObject":
        self.init_plot()
        return self

    def init_plot(self) -> None:
        super().init_plot()

    def update(self) -> None:
        super().update()
        # yaw_matrix = np.array(
        #     [
        #         [math.cos(self.yaw), -math.sin(self.yaw), 0],
        #         [math.sin(self.yaw), math.cos(self.yaw), 0],
        #         [0, 0, 1],
        #     ]
        # )
        # pitch_matrix = np.array(
        #     [
        #         [math.cos(self.pitch), 0, math.sin(self.pitch)],
        #         [0, 1, 0],
        #         [-math.sin(self.pitch), 0, math.cos(self.pitch)],
        #     ]
        # )
        # roll_matrix = np.array(
        #     [
        #         [1, 0, 0],
        #         [0, math.cos(self.roll), -math.sin(self.roll)],
        #         [0, math.sin(self.roll), math.cos(self.roll)],
        #     ]
        # )
        # rot_matrix = yaw_matrix @ pitch_matrix @ roll_matrix
        # u = [self.quaternion[1], self.quaternion[2], self.quaternion[3]]
        # s = self.quaternion[0]
        # new_points = list(
        # [
        # # np.matmul(vert, rot_matrix)
        # list(
        # np.array(
        # 2.0 * np.dot(u, np.array(v)) * u
        # + (s * s - np.dot(u, u)) * np.array(v)
        # + 2.0 * s * np.cross(u, np.array(v))  # type: ignore
        # )
        # for v in vert  # type: ignore
        # )
        # for vert in self.verts
        # ]
        # )
        new_points = list(
            [
                list(self.quaternion.rotate(v) for v in vert)  # type: ignore
                for vert in self.verts
            ]
        )
        # self.poly.set_verts(new_points)
        # self.poly.do_3d_projection()
        if self.image is not None:
            self.image.remove()

        self.poly = Poly3DCollection(verts=new_points)
        self.poly.set_edgecolor(self.color)
        self.poly.set_facecolor("black")
        self.image = self.plot.add_collection3d(self.poly)  # type: ignore

    def add_data(self, data: npt.NDArray[np.float64]) -> None:
        super().add_data(data)

    def add_point(self, quaternion: npt.NDArray[np.float64]) -> None:
        self.quaternion = pyquaternion.Quaternion(quaternion)

    def collect_images(self) -> list[matplotlib.artist.Artist]:
        return (
            [self.poly, self.image]
            if self.poly is not None and self.image is not None
            else []
        )
