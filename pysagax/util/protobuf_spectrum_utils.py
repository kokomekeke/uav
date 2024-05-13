import numpy as np
import pysagax.message.data_pb2 as proto_data
import pysagax.message.command_pb2 as proto_cmd

from typing import ValuesView

PROTOBUF_NUMPY_TYPE_MAPPING: dict[proto_data.Spectrum.DataType.ValueType, np.dtype] = {
    proto_data.Spectrum.DataType.INT16: np.dtype(np.int16),
    proto_data.Spectrum.DataType.INT8: np.dtype(np.int8),
    proto_data.Spectrum.DataType.FLOAT32: np.dtype(np.float32),
}


def protobuf_spectrum_to_numpy(spectrum: proto_data.Spectrum) -> np.ndarray:
    """
    Decoding a single spectrum data: returns the Spectrum.data as a numpy array.
    """
    np_data_type: np.dtype = PROTOBUF_NUMPY_TYPE_MAPPING[spectrum.data_type]
    spectrum_data = np.frombuffer(spectrum.data, np_data_type)
    return spectrum_data


def convert_iterable_to_spectrum_data(
    array: np.ndarray | list | ValuesView,
    type: proto_data.Spectrum.DataType.ValueType = proto_data.Spectrum.DataType.FLOAT32,
):
    """
    Converts numpy array, list or dict_values
    to bytes that can be added to proto_data.Spectrum.data.
    """
    return np.fromiter(array, PROTOBUF_NUMPY_TYPE_MAPPING[type]).tobytes()


def create_spectrum_with_freq_dict(
    spectrum: proto_data.Spectrum,
) -> dict[float, float | int]:
    """
    Takes a Spectrum packet and returns a dictionary with
    key-value pairs of frequency and amplitude for each bin.
    """

    spectrum_data = protobuf_spectrum_to_numpy(spectrum)

    min_freq = spectrum.center_frequency - spectrum.bandwidth / 2
    max_freq = spectrum.center_frequency + spectrum.bandwidth / 2
    bin_freqs = np.linspace(min_freq, max_freq, len(spectrum_data))

    # a dict of bin frequency -> bin amplitude.
    spectrum_with_freq = {f: a for f, a in list(zip(bin_freqs, spectrum_data))}

    return spectrum_with_freq


def apply_roi_on_spectrum(
    spectrum: proto_data.Spectrum | dict[float, float | int], roi: proto_cmd.ROIMask
) -> tuple[dict[float, float | int], dict[float, float | int]]:
    """
    Separating spectrum (or spectrum with freq dict) to signal (inside the roi) and noise (outside the roi) bins
    """
    if isinstance(spectrum, proto_data.Spectrum):
        spectrum = create_spectrum_with_freq_dict(spectrum)

    roi_min = roi.center_frequency - roi.span / 2
    roi_max = roi.center_frequency + roi.span / 2
    signal_bins = {f: a for f, a in spectrum.items() if roi_min <= f and f <= roi_max}
    noise_bins = {f: a for f, a in spectrum.items() if (roi_min > f or f > roi_max)}

    return signal_bins, noise_bins
