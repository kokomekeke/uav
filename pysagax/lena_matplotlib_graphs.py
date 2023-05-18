#
# Created by aron.szabo@sagaxcommunications.com on 15/05/2022.
#
from typing import Any, Optional

import matplotlib.cm
import numpy as np
import numpy.typing as npt
from matplotlib.animation import FuncAnimation  # type: ignore
from matplotlib.backend_bases import KeyEvent  # type: ignore
from matplotlib.backends.backend_tkagg import (  # type: ignore
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)


class GraphParameters:
    def __init__(self):
        self.iq_rate: int = 0
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
    def __init__(self, plot: matplotlib.axes.SubplotBase):
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

    def init_plot(self):
        pass

    def init_image(self):
        pass

    def make_plot(self):
        self.init_plot()
        return self

    def update(self):
        pass

    def add_data(self, data: npt.NDArray[np.float64]):
        pass

    def collect_images(self):
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
        return self.raise_if_exceeds(locs)

    def view_limits(self, dmin: float, dmax: float) -> tuple[float, float]:
        """
        Set the view limits
        """
        return matplotlib.transforms.nonsingular(dmin, dmax, expander=1e-12, tiny=1e-13)


class WaterfallMagnitudeGraph(GraphImage):
    def __init__(self, plot: matplotlib.axes.SubplotBase, params: GraphParameters):
        super().__init__(plot)
        self.params = params
        self.waterfall = np.ones([self.params.waterfall_size, self.params.bin_count])
        """
        Magnitude waterfall data (numpy matrix)
        """

        self.vmin: float = -100
        self.vmax: float = 0

    def bin_freq_formatter(self, x: float, pos: Any = None) -> str:
        return f"{((x - self.params.bin_count / 2) * (self.params.iq_rate / self.params.bin_count) + self.params.center_frequency) / 1e6:.3f}M"

    def sample_id_formatter(self, x: float, pos: Any = None) -> str:
        return f"{x - self.params.waterfall_size:.0f}"

    def magnitude_format_coord(self, x: float, y: float) -> str:
        return f"Frequency: {self.bin_freq_formatter(x)} (bin {int(x)}), Packet: {self.sample_id_formatter(y)}"

    def initialize(self):
        self.init_image()
        return self

    def init_image(self):
        super().init_image()
        assert self.plot is not None
        self.waterfall = np.zeros([self.params.waterfall_size, self.params.bin_count])
        self.image = self.plot.imshow(
            self.waterfall,
            cmap=matplotlib.cm.get_cmap("gnuplot"),
            animated=True,
            vmax=self.vmax,
            vmin=self.vmin,
        )

    def init_plot(self):
        super().init_plot()
        assert self.plot is not None
        self.plot.xaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(self.bin_freq_formatter)
        )
        self.plot.xaxis.set_major_locator(HalfLocator(max=self.params.bin_count))
        self.plot.tick_params(axis="x", labelrotation=45)
        self.plot.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(self.sample_id_formatter)
        )
        self.plot.format_coord = self.magnitude_format_coord
        # self.fig_ref.colorbar(self.magnitude_image)

        self.plot.set_label("Magnitude")
        self.plot.set_ylabel("Packets")
        self.plot.set_aspect("auto")

    def update(self):
        super().update()
        self.image.set_data(self.waterfall)

    def add_data(self, data: npt.NDArray[np.float64]):
        super().add_data(data)
        self.waterfall = np.append(
            self.waterfall[-self.params.waterfall_size + 1 :, :],
            np.array([data]),
            axis=0,
        )


class AngleSpectrumGraph(GraphImage):
    def __init__(self, plot: matplotlib.axes.SubplotBase, params: GraphParameters):
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
        return f"{((x - self.params.bin_count / 2) * (self.params.iq_rate / self.params.bin_count) + self.center_frequency) / 1e6:.3f}M"

    def angle_format_coord(self, x: float, y: float) -> str:
        if 0 < x < len(self.spectrum):
            val = self.spectrum[int(x)]
        else:
            val = 0
        return (
            f"Frequency: {self.bin_freq_formatter(x)} (bin {int(x)}), "
            f"Angle: {val:.3f} rad ({val / np.pi * 180:.2f} deg)"
        )

    def init_image(self):
        super().init_image()
        self.spectrum = np.zeros([self.params.bin_count])
        self.image = self.plot.plot(
            self.spectrum, lw=1, color=self.color, animated=True
        )[0]
        self.marker_image = self.plot.plot(0, 0, "or", animated=True)[0]

    def initialize(self, color: str):
        self.color = color
        self.init_image()
        return self

    def init_plot(self, plot: matplotlib.axes.SubplotBase):
        super().init_plot(plot)
        assert self.plot is not None
        self.plot.xaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(self.bin_freq_formatter)
        )

        self.plot.xaxis.set_major_locator(HalfLocator(max=self.params.bin_count))
        self.plot.tick_params(axis="x", labelrotation=45)
        self.plot.yaxis.set_major_formatter(
            matplotlib.ticker.StrMethodFormatter("{x:.2f}")
        )
        self.plot.grid(axis="both")
        self.plot.format_coord = self.angle_format_coord
        self.plot.set_ylim(-np.pi, np.pi)
        self.plot.set_yticks([-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi])
        self.plot.set_yticklabels(
            [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
        )
        self.plot.set_aspect("auto")

    def update(self):
        super().update()
        self.image.set_ydata(self.spectrum)
        self.marker_image.set_xdata(self.marker_bin)
        self.marker_image.set_ydata(self.marker_value)

    def add_data(self, data: npt.NDArray[np.float64]):
        super().add_data(data)
        self.set_data(data)

    def set_data(self, data: npt.NDArray[np.float64]):
        self.spectrum = data


class WaterfallAngleGraph(GraphImage):
    def __init__(self, plot: matplotlib.axes.SubplotBase, params: GraphParameters):
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

    def sample_id_formatter(self, x: float, pos: Any = None) -> str:
        return f"{x - self.params.waterfall_size:.0f}"

    def roi_format_coord(self, x: float, y: float) -> str:
        return (
            f"Packet: {self.sample_id_formatter(y)}, "
            f"Angle: {x:.3f} rad ({x / np.pi * 180:.2f} deg)"
        )

    def init_image(self):
        super().init_image()
        assert self.plot is not None
        self.image = self.plot.plot(
            self.waterfall,
            np.arange(0, self.params.waterfall_size),
            lw=1,
            color=self.color,
            animated=True,
            label=self.label,
        )[0]

    def initialize(self, color: str, label: str):
        self.color = color
        self.label = label
        self.init_image()
        return self

    def init_plot(self):
        super().init_plot()

        self.plot.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(self.sample_id_formatter)
        )
        self.plot.set_ylabel("Packets")
        self.plot.set_aspect("auto")

        self.plot.xaxis.set_major_formatter(lambda x, y: f"{x/np.pi:.2f}{pi_chr}")
        self.plot.grid(axis="both")

        self.plot.set_xlim(-np.pi, np.pi)
        self.plot.xaxis.set_major_locator(HalfLocator(min=-np.pi, max=np.pi))
        # self.plot.set_xticks(
        #    [-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi]
        # )
        # self.plot.set_xticklabels(
        #    [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
        # )
        self.plot.format_coord = self.roi_format_coord
        self.plot.set_label(self.plot_label)
        self.plot.set_aspect("auto")
        self.plot.invert_yaxis()
        self.plot.set_ylim(self.params.waterfall_size, 0)
        self.plot.yaxis.set_label_position("right")
        self.plot.yaxis.tick_right()
        self.plot.legend()

    def update(self):
        super().update()
        self.image.set_xdata(self.waterfall)

    def add_data(self, data: npt.NDArray[np.float64]):
        super().add_data(data)

    def add_point(self, point: Optional[float]):
        self.waterfall = np.append(
            self.waterfall[-self.params.waterfall_size + 1 :],
            np.array([point]),
            axis=0,
        )
