import pytest
from pysagax.util.protobuf_spectrum_utils import (
    protobuf_spectrum_to_numpy,
    convert_iterable_to_spectrum_data,
    create_spectrum_with_freq_dict,
)
import pysagax.message.data_pb2 as proto_data
import numpy as np


@pytest.mark.parametrize(
    ["spectrum_array", "data_type"],
    [
        [[0, 1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT8],
        [[0, 1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT16],
        [[0, 1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32],
        [[-1, -2, -3], proto_data.Spectrum.DataType.INT8],
        [[-1, -2, -3], proto_data.Spectrum.DataType.INT16],
        [[-1, -2, -3], proto_data.Spectrum.DataType.FLOAT32],
        # [[i for i in range(-1000, 1000)], proto_data.Spectrum.DataType.INT8],
        [[i for i in range(-1000, 1000)], proto_data.Spectrum.DataType.INT16],
        [[i for i in range(-1000, 1000)], proto_data.Spectrum.DataType.FLOAT32],
        # [[194]*600, proto_data.Spectrum.DataType.INT8],
        [[194] * 600, proto_data.Spectrum.DataType.INT16],
        [[194] * 600, proto_data.Spectrum.DataType.FLOAT32],
        # Same input vectors but as numpy arrays:
        [[], proto_data.Spectrum.DataType.INT8],
        [[], proto_data.Spectrum.DataType.INT16],
        [[], proto_data.Spectrum.DataType.FLOAT32],
        [np.array([0, 1, 2, 3, 4, 5]), proto_data.Spectrum.DataType.INT8],
        [np.array([0, 1, 2, 3, 4, 5]), proto_data.Spectrum.DataType.INT16],
        [np.array([0, 1, 2, 3, 4, 5]), proto_data.Spectrum.DataType.FLOAT32],
        [np.array([-1, -2, -3]), proto_data.Spectrum.DataType.INT8],
        [np.array([-1, -2, -3]), proto_data.Spectrum.DataType.INT16],
        [np.array([-1, -2, -3]), proto_data.Spectrum.DataType.FLOAT32],
        # [np.array([i for i in range(-1000, 1000)]), proto_data.Spectrum.DataType.INT8],
        [np.array([i for i in range(-1000, 1000)]), proto_data.Spectrum.DataType.INT16],
        [
            np.array([i for i in range(-1000, 1000)]),
            proto_data.Spectrum.DataType.FLOAT32,
        ],
        # [np.array([194]*600), proto_data.Spectrum.DataType.INT8],
        [np.array([194] * 600), proto_data.Spectrum.DataType.INT16],
        [np.array([194] * 600), proto_data.Spectrum.DataType.FLOAT32],
        [np.array([]), proto_data.Spectrum.DataType.INT8],
        [np.array([]), proto_data.Spectrum.DataType.INT16],
        [np.array([]), proto_data.Spectrum.DataType.FLOAT32],
        # Input vectors as dict_values:
        [{10: 0, 11: 1, 12: 2, 13: 3, 14: 4, 15: 5}, proto_data.Spectrum.DataType.INT8],
        [
            {10: 0, 11: 1, 12: 2, 13: 3, 14: 4, 15: 5},
            proto_data.Spectrum.DataType.INT16,
        ],
        [
            {10: 0, 11: 1, 12: 2, 13: 3, 14: 4, 15: 5},
            proto_data.Spectrum.DataType.FLOAT32,
        ],
        # [{a:(1000-a) for a, b in range(-1000, 1000)}, proto_data.Spectrum.DataType.INT8],
        [
            {a: (1000 - a) for a in range(-1000, 1000)},
            proto_data.Spectrum.DataType.INT16,
        ],
        [
            {a: (1000 - a) for a in range(-1000, 1000)},
            proto_data.Spectrum.DataType.FLOAT32,
        ],
    ],
)
def test_spectrum_utils_chained(spectrum_array, data_type):
    """
    Converting an array or list or dict_values to spectrum data and then back.
    """
    # Creating spectrum from spectrum_array using convert_iterable_to_spectrum_data()
    s = proto_data.Spectrum(data_type=data_type)
    s.data = convert_iterable_to_spectrum_data(spectrum_array, s.data_type)

    # Creating a numpy array from spectrum
    new_array = protobuf_spectrum_to_numpy(s)

    # Checking if new_array contains the same data as the original spectrum_array
    for a, b in zip(spectrum_array, new_array):
        assert a - b < 1e-6

    # check if the size of s.data is as expected
    match data_type:
        case proto_data.Spectrum.DataType.INT8:
            byte_per_bin = 1
        case proto_data.Spectrum.DataType.INT16:
            byte_per_bin = 2
        case proto_data.Spectrum.DataType.FLOAT32:
            byte_per_bin = 4
    assert len(s.data) == byte_per_bin * len(spectrum_array)


@pytest.mark.parametrize(
    ["spectrum", "center_freq", "bandwidth", "expected"],
    [
        [[1.0, 2.0, 3.0, 4.0, 5.0], 10, 4, {8: 1, 9: 2, 10: 3, 11: 4, 12: 5}],
        [
            [-1, -2, -3, -4, -5],
            1000,
            400,
            {800: -1, 900: -2, 1000: -3, 1100: -4, 1200: -5},
        ],
        [[], 1000, 400, {}],
        [[1], 1000, 0, {1000: 1}],
        [[1, 2], 1000, 1000, {500: 1, 1500: 2}],
    ],
)
def test_create_spectrum_with_freq_dict(spectrum, center_freq, bandwidth, expected):
    s = proto_data.Spectrum()
    s.data = convert_iterable_to_spectrum_data(spectrum)
    s.data_type = proto_data.Spectrum.DataType.FLOAT32
    s.center_frequency = center_freq
    s.bandwidth = bandwidth

    spectrum_with_freqs = create_spectrum_with_freq_dict(s)
    assert expected == spectrum_with_freqs


def test_create_spectrum_with_freq_dict_empty_spectrum():
    s = proto_data.Spectrum()
    spectrum_with_freqs = create_spectrum_with_freq_dict(s)
    assert spectrum_with_freqs == {}
