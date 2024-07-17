import numpy as np

from pysagax.df.compass_sensors import (
    AaroniaParser,
    CalibrationStatus,
    CompassParser,
    CompassSensor,
    SimpleParser,
    open_aaronia_serial_dev,
    open_aaronia_socket_dev,
    open_arduino_serial_dev,
)
from pysagax.df.df_classes import DDF260, DfModule, DfResult, LenaDf
from pysagax.df.lena_core_service import (
    BaseConnection,
    CoreServiceDebugPacket,
    CoreServiceEOFPacket,
    CoreServicePacket,
    CoreServiceParser,
    CoreServiceROILackOfSignalPacket,
    CoreServiceROIResultPacket,
    CoreServiceSpectrumPacket,
    StreamConnectionProcess,
)
from pysagax.df.lena_with_compass import StreamAndCompassProcess
from pysagax.heading.heading_sources import HeadingSource, HeadingStatic
from pysagax.source.source_manager import SourceManager
from pysagax.ui.autocomplete_command_box import AutocompleteCommandBox
from pysagax.ui.lena_matplotlib_graphs import (
    AngleSpectrumGraph,
    CompassGraph,
    CompassGraphWithDeviation,
    GraphImage,
    GraphParameters,
    MagnitudeSpectrumGraph,
    ThreeDimensionGraph,
    ThreeDimensionObject,
    WaterfallAngleGraph,
    WaterfallMagnitudeGraph,
)
from pysagax.ui.plot_frame import PlotFrame, PlotSettingsFrame
from pysagax.ui.custom_widgets import ToggleButton, EntryWithLabel
from pysagax.ui.octave_data import save_octave
from pysagax.ui.plot_frame import PlotFrame, PlotSettingsFrame
from pysagax.util.mat import normalize_angle, si_to_float

__all__ = [
    "CoreServicePacket",
    "CoreServiceSpectrumPacket",
    "CoreServiceEOFPacket",
    "CoreServiceDebugPacket",
    "CoreServiceROIResultPacket",
    "CoreServiceROILackOfSignalPacket",
    "BaseConnection",
    "StreamConnectionProcess",
    "CoreServiceParser",
    "GraphParameters",
    "GraphImage",
    "AngleSpectrumGraph",
    "WaterfallMagnitudeGraph",
    "WaterfallAngleGraph",
    "MagnitudeSpectrumGraph",
    "ThreeDimensionGraph",
    "ThreeDimensionObject",
    "CompassGraph",
    "AutocompleteCommandBox",
    "CompassSensor",
    "SimpleParser",
    "AaroniaParser",
    "CalibrationStatus",
    "open_aaronia_serial_dev",
    "open_arduino_serial_dev",
    "open_aaronia_socket_dev",
    "save_octave",
    "DfResult",
    "DfModule",
    "DDF260",
    "LenaDf",
    "si_to_float",
    "normalize_angle",
    "StreamAndCompassProcess",
    "HeadingSource",
    "SourceManager",
]

from . import _version

__version__ = _version.get_versions()["version"]
if "0+unknown" in __version__ or not __version__:
    try:
        import pkg_resources
        __version__ = pkg_resources.get_distribution('pysagax').version
    except:
        __version__ = "0+unknown"
