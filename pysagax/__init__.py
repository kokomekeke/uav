import numpy as np

from pysagax.df.compass_sensors import (AaroniaParser, CalibrationStatus,
                                        CompassParser, CompassSensor,
                                        SimpleParser, open_aaronia_serial_dev,
                                        open_aaronia_socket_dev,
                                        open_arduino_serial_dev)
from pysagax.df.df_classes import DDF260, DfModule, DfResult, LenaDf
from pysagax.df.lena_core_service import (BaseConnection,
                                          CoreServiceDebugPacket,
                                          CoreServiceEOFPacket,
                                          CoreServicePacket, CoreServiceParser,
                                          CoreServiceROILackOfSignalPacket,
                                          CoreServiceROIResultPacket,
                                          CoreServiceSpectrumPacket,
                                          StreamConnectionProcess)
from pysagax.df.lena_with_compass import StreamAndCompassProcess
from pysagax.ui.autocomplete_command_box import AutocompleteCommandBox
from pysagax.ui.lena_matplotlib_graphs import (AngleSpectrumGraph,
                                               CompassGraph, GraphImage,
                                               GraphParameters,
                                               MagnitudeSpectrumGraph,
                                               ThreeDimensionGraph,
                                               ThreeDimensionObject,
                                               WaterfallAngleGraph,
                                               WaterfallMagnitudeGraph)
from pysagax.ui.octave_data import save_octave


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
    
def normalize_angle(angle: float) -> float:
    while angle > np.pi:
        angle = angle - 2 * np.pi
    while angle <= -np.pi:
        angle = angle + 2 * np.pi
    return angle


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
    "StreamAndCompassProcess",
]

from . import _version

__version__ = _version.get_versions()['version']

from . import _version
__version__ = _version.get_versions()['version']
