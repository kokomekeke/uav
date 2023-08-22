from pysagax.lena_core_service import (
    CoreServicePacket,
    BaseConnection,
    StreamConnectionProcess,
    StreamProcessingThread,
)
from pysagax.lena_matplotlib_graphs import (
    GraphParameters,
    GraphImage,
    AngleSpectrumGraph,
    WaterfallAngleGraph,
    WaterfallMagnitudeGraph,
    ThreeDimensionGraph,
    ThreeDimensionObject,
    CompassGraph,
)
from pysagax.autocomplete_command_box import AutocompleteCommandBox
from pysagax.compass_sensors import (
    CompassParser,
    AaroniaParser,
    SimpleParser,
    CompassSensor,
    open_aaronia_serial_dev,
    open_arduino_serial_dev,
    open_aaronia_socket_dev,
    CalibrationStatus,
)
from pysagax.df_classes import DfModule, DfResult, DDF260, LenaDf
from pysagax.octave_data import save_octave


def si_to_float(si: str) -> float:
    prefix = {
        "y": 1e-24,  # yocto
        "z": 1e-21,  # zepto
        "a": 1e-18,  # atto
        "f": 1e-15,  # femto
        "p": 1e-12,  # pico
        "n": 1e-9,  # nano
        "u": 1e-6,  # micro
        "m": 1e-3,  # mili
        "c": 1e-2,  # centi
        "d": 1e-1,  # deci
        "k": 1e3,  # kilo
        "M": 1e6,  # mega
        "G": 1e9,  # giga
        "T": 1e12,  # tera
        "P": 1e15,  # peta
        "E": 1e18,  # exa
        "Z": 1e21,  # zetta
        "Y": 1e24,  # yotta
    }
    si = si.strip()
    if si[-1] in prefix.keys():
        return float(si[:-1]) * prefix[si[-1]]
    else:
        return float(si)


__all__ = [
    "CoreServicePacket",
    "BaseConnection",
    "StreamConnectionProcess",
    "StreamProcessingThread",
    "GraphParameters",
    "GraphImage",
    "AngleSpectrumGraph",
    "WaterfallMagnitudeGraph",
    "WaterfallAngleGraph",
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
]
