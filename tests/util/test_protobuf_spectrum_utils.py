import pytest
from pysagax.util.protobuf_spectrum_utils import (
    protobuf_spectrum_to_numpy,
    convert_iterable_to_spectrum_data,
    cast_spectrum_data_type,
    cast_all_spectrums_in_measurement,
)
import pysagax.message.data_pb2 as proto_data
import pysagax.message.command_pb2 as proto_cmd
import numpy as np
from pysagax.util.protobuf_spectrum_utils import Spectrum


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


class TestSpectrumCasting:
    """Tests cast_spectrum_data_type() and cast_all_spectrums_in_measurement()"""

    @pytest.mark.parametrize(
        ["spectrum", "dtype", "expected"],
        [
            [  # CASE 1
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.FLOAT32,
                    data=convert_iterable_to_spectrum_data(
                        [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                    ),
                ),
                proto_data.Spectrum.DataType.INT16,
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.INT16,
                    data=convert_iterable_to_spectrum_data(
                        [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT16
                    ),
                ),
            ],
            [  # CASE 2: float to int with rounding
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.FLOAT32,
                    data=convert_iterable_to_spectrum_data(
                        [i / 10 for i in range(1000)],
                        proto_data.Spectrum.DataType.FLOAT32,
                    ),
                ),
                proto_data.Spectrum.DataType.INT8,
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.INT8,
                    data=convert_iterable_to_spectrum_data(
                        [i / 10 for i in range(1000)], proto_data.Spectrum.DataType.INT8
                    ),
                ),
            ],
            [  # CASE 3: int to float with rounding
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.INT16,
                    data=convert_iterable_to_spectrum_data(
                        [i / 10 for i in range(1000)],
                        proto_data.Spectrum.DataType.INT16,
                    ),
                ),
                proto_data.Spectrum.DataType.FLOAT32,
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.FLOAT32,
                    data=convert_iterable_to_spectrum_data(
                        [np.floor(i / 10) for i in range(1000)],
                        proto_data.Spectrum.DataType.FLOAT32,
                    ),
                ),
            ],
        ],
    )
    def test_cast_spectrum_data_type(self, spectrum, dtype, expected):
        """Tests cast_spectrum_data_type with inplace=False"""
        original_spectrum = proto_data.Spectrum()
        original_spectrum.CopyFrom(spectrum)

        result = cast_spectrum_data_type(spectrum, dtype)

        assert result == expected
        # inplace = False -> spectrum shouldn't change
        assert spectrum == original_spectrum

    @pytest.mark.parametrize(
        ["spectrum", "dtype", "expected"],
        [
            [  # CASE 1
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.FLOAT32,
                    data=convert_iterable_to_spectrum_data(
                        [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                    ),
                ),
                proto_data.Spectrum.DataType.INT16,
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.INT16,
                    data=convert_iterable_to_spectrum_data(
                        [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT16
                    ),
                ),
            ],
            [  # CASE 2: float to int with rounding
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.FLOAT32,
                    data=convert_iterable_to_spectrum_data(
                        [i / 10 for i in range(1000)],
                        proto_data.Spectrum.DataType.FLOAT32,
                    ),
                ),
                proto_data.Spectrum.DataType.INT8,
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                    data_type=proto_data.Spectrum.DataType.INT8,
                    data=convert_iterable_to_spectrum_data(
                        [i / 10 for i in range(1000)], proto_data.Spectrum.DataType.INT8
                    ),
                ),
            ],
            [  # CASE 3: int to float with rounding
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.AZIMUTH,
                    data_type=proto_data.Spectrum.DataType.INT16,
                    data=convert_iterable_to_spectrum_data(
                        [i / 10 for i in range(1000)],
                        proto_data.Spectrum.DataType.INT16,
                    ),
                ),
                proto_data.Spectrum.DataType.FLOAT32,
                proto_data.Spectrum(
                    channel_id=1,
                    spectrum_type=proto_data.Spectrum.SpectrumType.AZIMUTH,
                    data_type=proto_data.Spectrum.DataType.FLOAT32,
                    data=convert_iterable_to_spectrum_data(
                        [np.floor(i / 10) for i in range(1000)],
                        proto_data.Spectrum.DataType.FLOAT32,
                    ),
                ),
            ],
        ],
    )
    def test_cast_spectrum_data_type_inplace(self, spectrum, dtype, expected):
        """Tests cast_spectrum_data_type with inplace=True"""
        original_spectrum = proto_data.Spectrum()
        original_spectrum.CopyFrom(spectrum)

        result = cast_spectrum_data_type(spectrum, dtype, inplace=True)

        assert result == None
        assert spectrum == expected
        # inplace = True -> spectrum should change
        assert spectrum != original_spectrum

    @pytest.mark.parametrize(
        ["measurement", "dtype", "expected"],
        [
            [  # CASE 1
                proto_data.Measurement(
                    data=[
                        proto_data.Spectrum(
                            channel_id=1,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        )
                    ],
                    quaternion=[1, 2, 3, 4],
                ),
                proto_data.Spectrum.DataType.INT16,
                proto_data.Measurement(
                    data=[
                        proto_data.Spectrum(
                            channel_id=1,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.INT16,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT16
                            ),
                        )
                    ],
                    quaternion=[1, 2, 3, 4],
                ),
            ],
            [  # CASE 2: multiple spectrums with different data and spectrum types
                proto_data.Measurement(
                    data=[
                        proto_data.Spectrum(
                            channel_id=1,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.INT16,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT16
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=2,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.INT8,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT8
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=0,
                            spectrum_type=proto_data.Spectrum.SpectrumType.ELEVATION,
                            data_type=proto_data.Spectrum.DataType.INT8,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT8
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=0,
                            spectrum_type=proto_data.Spectrum.SpectrumType.AZIMUTH,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                    ],
                    quaternion=[1, 2, 3, 4],
                ),
                proto_data.Spectrum.DataType.FLOAT32,
                proto_data.Measurement(
                    data=[
                        proto_data.Spectrum(
                            channel_id=1,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=2,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=0,
                            spectrum_type=proto_data.Spectrum.SpectrumType.ELEVATION,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=0,
                            spectrum_type=proto_data.Spectrum.SpectrumType.AZIMUTH,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                    ],
                    quaternion=[1, 2, 3, 4],
                ),
            ],
        ],
    )
    def test_cast_all_spectrums_in_measurement(self, measurement, dtype, expected):
        """Tests cast_all_spectrums_in_measurement with inplace=False"""
        original_measurement = proto_data.Measurement()
        original_measurement.CopyFrom(measurement)

        result = cast_all_spectrums_in_measurement(measurement, dtype)

        # assert result == None
        assert result == expected
        # inplace = False -> spectrum shouldn't change
        assert measurement == original_measurement

    @pytest.mark.parametrize(
        ["measurement", "dtype", "expected"],
        [
            [  # CASE 1
                proto_data.Measurement(
                    data=[
                        proto_data.Spectrum(
                            channel_id=1,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        )
                    ],
                    quaternion=[1, 2, 3, 4],
                ),
                proto_data.Spectrum.DataType.INT16,
                proto_data.Measurement(
                    data=[
                        proto_data.Spectrum(
                            channel_id=1,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.INT16,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT16
                            ),
                        )
                    ],
                    quaternion=[1, 2, 3, 4],
                ),
            ],
            [  # CASE 2: multiple spectrums with different data and spectrum types
                proto_data.Measurement(
                    data=[
                        proto_data.Spectrum(
                            channel_id=1,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.INT16,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT16
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=2,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.INT8,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT8
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=0,
                            spectrum_type=proto_data.Spectrum.SpectrumType.ELEVATION,
                            data_type=proto_data.Spectrum.DataType.INT8,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.INT8
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=0,
                            spectrum_type=proto_data.Spectrum.SpectrumType.AZIMUTH,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                    ],
                    quaternion=[1, 2, 3, 4],
                ),
                proto_data.Spectrum.DataType.FLOAT32,
                proto_data.Measurement(
                    data=[
                        proto_data.Spectrum(
                            channel_id=1,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=2,
                            spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=0,
                            spectrum_type=proto_data.Spectrum.SpectrumType.ELEVATION,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                        proto_data.Spectrum(
                            channel_id=0,
                            spectrum_type=proto_data.Spectrum.SpectrumType.AZIMUTH,
                            data_type=proto_data.Spectrum.DataType.FLOAT32,
                            data=convert_iterable_to_spectrum_data(
                                [1, 2, 3, 4, 5], proto_data.Spectrum.DataType.FLOAT32
                            ),
                        ),
                    ],
                    quaternion=[1, 2, 3, 4],
                ),
            ],
        ],
    )
    def test_cast_all_spectrums_in_measurement_inplace(
        self, measurement, dtype, expected
    ):
        """Tests cast_all_spectrums_in_measurement with inplace=True"""
        original_measurement = proto_data.Measurement()
        original_measurement.CopyFrom(measurement)

        result = cast_all_spectrums_in_measurement(measurement, dtype, inplace=True)

        assert result == None
        assert measurement == expected
        # inplace = True -> spectrum should change
        assert measurement != original_measurement


class TestSpectrum:
    @pytest.mark.parametrize(
        ["data", "f_center", "span", "exp_delta_f", "exp_start"],
        [
            [[1, 2, 3], 10, 2, 1, 9],
            [[2], 10, 2, 2, 10],
            [[i for i in range(1000, 2001)], 1500, 1000, 1, 1000],
        ],
    )
    def test_init(self, data, f_center, span, exp_delta_f, exp_start):
        spectrum = Spectrum(data, f_center, span)
        assert spectrum.delta_f == exp_delta_f
        assert spectrum.f_start == exp_start

    @pytest.mark.parametrize(
        ["data", "data_type", "f_center", "span", "exp_delta_f", "exp_start"],
        [
            [[1, 2, 3], proto_data.Spectrum.DataType.INT16, 10, 2, 1, 9],
            [[2], proto_data.Spectrum.DataType.INT16, 10, 2, 2, 10],
            [
                [i for i in range(1000, 2001)],
                proto_data.Spectrum.DataType.INT16,
                1500,
                1000,
                1,
                1000,
            ],
        ],
    )
    def test_from_proto_spectrum(
        self, data, data_type, f_center, span, exp_delta_f, exp_start
    ):
        proto_s = proto_data.Spectrum(data_type=data_type)
        proto_s.data = convert_iterable_to_spectrum_data(data, proto_s.data_type)
        proto_s.center_frequency = f_center
        proto_s.bandwidth = span

        spectrum = Spectrum.from_proto_spectrum(proto_s)

        assert np.all(spectrum.data == data)
        assert spectrum.f_center == f_center
        assert spectrum.delta_f == exp_delta_f
        assert spectrum.f_start == exp_start

    @pytest.mark.parametrize(
        ["spectrum", "freq", "expected"],
        [
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 10, 2],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 12, 4],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 8, 0],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 10.4, 2],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 9.6, 2],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 10, 2],
            # Test with 1 bin:
            [Spectrum([3.0], 10, 4), 8, 0],
            [Spectrum([3.0], 10, 4), 9, 0],
            [Spectrum([3.0], 10, 4), 10, 0],
            [Spectrum([3.0], 10, 4), 12, 0],
            # 1001 bins from 1000Hz to 2000Hz:
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 1248, 248],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 1247.6, 248],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 1248.4, 248],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 999.6, 0],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 2000.4, 1000],
        ],
    )
    def test_get_index_from_freq(self, spectrum, freq, expected):

        index = spectrum.get_index_from_freq(freq)
        assert index == expected

    @pytest.mark.parametrize(
        ["spectrum", "freq"],
        [
            # Test with 1 bin:
            [Spectrum([3.0], 10, 4), 7.9],
            [Spectrum([3.0], 10, 4), 12.1],
            # 1001 bins from 1000Hz to 2000Hz:
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 999.4],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 2000.6],
        ],
    )
    def test_get_index_from_freq_error(self, spectrum, freq):
        """Tests when the given frequency is outside of the span of the spectrum"""
        with pytest.raises(ValueError):
            spectrum.get_index_from_freq(freq)

    @pytest.mark.parametrize(
        ["spectrum", "freq", "expected"],
        [
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 10, 103],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 12, 105],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 8, 101],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 10.4, 103],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 9.6, 103],
            # Test with 1 bin:
            [Spectrum([3.0], 10, 4), 8, 3],
            [Spectrum([3.0], 10, 4), 9, 3],
            [Spectrum([3.0], 10, 4), 10, 3],
            [Spectrum([3.0], 10, 4), 12, 3],
            # 1001 bins from 1000Hz to 2000Hz:
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 1248, 1248],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 1247.6, 1248],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 1248.4, 1248],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 999.6, 1000],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 2000.4, 2000],
        ],
    )
    def test_get_value_from_freq(self, spectrum, freq, expected):
        amplitude = spectrum.get_value_from_freq(freq)
        assert amplitude == expected

    @pytest.mark.parametrize(
        ["spectrum", "index", "expected"],
        [
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 2, 10],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 4, 12],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 0, 8],
            # Test with 1 bin:
            [Spectrum([3.0], 10, 4), 0, 10],
            # 1001 bins from 1000Hz to 2000Hz:
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 248, 1248],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 0, 1000],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 1000, 2000],
        ],
    )
    def test_get_freq_from_index(self, spectrum, index, expected):
        freq = spectrum.get_freq_from_index(index)
        assert freq - expected < 1e-6

    @pytest.mark.parametrize(
        ["spectrum", "index"],
        [
            [Spectrum([101, 102, 103, 104, 105], 10, 4), -1],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 5],
            [Spectrum([101, 102, 103, 104, 105], 10, 4), 14],
            # Test with 1 bin:
            [Spectrum([3.0], 10, 4), -1],
            [Spectrum([3.0], 10, 4), 1],
            # 1001 bins from 1000Hz to 2000Hz:
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), -112],
            [Spectrum([i for i in range(1000, 2001)], 1500, 1000), 5424],
        ],
    )
    def test_get_freq_from_index_out_of_range(self, spectrum, index):
        with pytest.raises(IndexError):
            freq = spectrum.get_freq_from_index(index)

    @pytest.mark.parametrize(
        ["spectrum", "roi_f_start", "roi_f_stop", "expected"],
        [
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                9,
                11,
                Spectrum([102, 103, 104], 10, 2),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                8.75,
                9.25,
                Spectrum([102], 9, 1),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                9.5,
                10.5,
                Spectrum([103], 10, 1),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                9.1,
                10.9,
                Spectrum([103], 10, 1.9),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                5,
                15,
                Spectrum([101, 102, 103, 104, 105], 10, 4),
            ],
            # Test with 1 bin (the span of the returned spectrum will be 0, but a spectrum with 1 bin is not really useful anyway):
            [Spectrum([3.0], 10, 4), 5, 10, Spectrum([3], 10, 4)],
            [Spectrum([3.0], 10, 4), 0, 10, Spectrum([3], 10, 4)],
            # # # 1001 bins from 1000Hz to 2000Hz:
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                1699,
                1701,
                Spectrum([1699, 1700, 1701], 1700, 2),
            ],
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                1600,
                1800,
                Spectrum([i for i in range(1600, 1801)], 1700, 200),
            ],
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                700,
                2700,
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
            ],
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                1700,
                2100,
                Spectrum([i for i in range(1700, 2001)], 1850, 300),
            ],
        ],
    )
    def test_get_spectrum_from_freq_range(
        self, spectrum, roi_f_start, roi_f_stop, expected
    ):
        result = spectrum._get_spectrum_from_freq_range(roi_f_start, roi_f_stop)

        assert (result.data == expected.data).all()
        assert result.f_center - expected.f_center < 1e-6
        assert result.span - expected.span < 1e-6

    @pytest.mark.parametrize(
        ["spectrum", "roi_f_start", "roi_f_stop", "expected", "expected_noise_bins"],
        [
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                9,
                11,
                Spectrum([102, 103, 104], 10, 2),
                [101, 105],
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                8.75,
                9.25,
                Spectrum([102], 9, 1),
                [101, 103, 104, 105],
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                5,
                15,
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                [],
            ],
            # Test with 1 bin (the span of the returned spectrum will be 0, but a spectrum with 1 bin is not really useful anyway):
            [Spectrum([3.0], 10, 4), 5, 10, Spectrum([3], 10, 4), []],
            [Spectrum([3.0], 10, 4), 0, 10, Spectrum([3], 10, 4), []],
            # # # 1001 bins from 1000Hz to 2000Hz:
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                1700,
                2100,
                Spectrum([i for i in range(1700, 2001)], 1850, 300),
                [i for i in range(1000, 1700)],
            ],
        ],
    )
    def test_get_spectrum_from_freq_range_noise_bins(
        self, spectrum, roi_f_start, roi_f_stop, expected, expected_noise_bins
    ):
        """Tests _get_spectrum_from_freq_range() with return_noise_bins=True"""
        result, noise_bins = spectrum._get_spectrum_from_freq_range(
            roi_f_start, roi_f_stop, return_noise_bins=True
        )

        assert (result.data == expected.data).all()
        assert result.f_center - expected.f_center < 1e-6
        assert result.span - expected.span < 1e-6
        assert (np.abs(noise_bins - np.array(expected_noise_bins)) < 1e-6).all()

    @pytest.mark.parametrize(
        ["spectrum", "roi", "expected"],
        [
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                proto_cmd.ROIMask(center_frequency=10, span=2),
                Spectrum([102, 103, 104], 10, 2),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                proto_cmd.ROIMask(center_frequency=9, span=0.5),
                Spectrum([102], 9, 1),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                proto_cmd.ROIMask(center_frequency=10, span=1),
                Spectrum([103], 10, 1),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                proto_cmd.ROIMask(center_frequency=10, span=1.9),
                Spectrum([103], 10, 1.9),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                proto_cmd.ROIMask(center_frequency=10, span=10),
                Spectrum([101, 102, 103, 104, 105], 10, 4),
            ],
            # Test with 1 bin (the span of the returned spectrum will be 0, but a spectrum with 1 bin is not really useful anyway):
            [
                Spectrum([3.0], 10, 4),
                proto_cmd.ROIMask(center_frequency=10, span=10),
                Spectrum([3], 10, 4),
            ],
            [
                Spectrum([3.0], 10, 4),
                proto_cmd.ROIMask(center_frequency=5, span=10),
                Spectrum([3], 10, 4),
            ],
            # # # 1001 bins from 1000Hz to 2000Hz:
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                proto_cmd.ROIMask(center_frequency=1700, span=2),
                Spectrum([1699, 1700, 1701], 1700, 2),
            ],
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                proto_cmd.ROIMask(center_frequency=1700, span=200),
                Spectrum([i for i in range(1600, 1801)], 1700, 200),
            ],
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                proto_cmd.ROIMask(center_frequency=1700, span=2000),
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
            ],
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                proto_cmd.ROIMask(center_frequency=1900, span=400),
                Spectrum([i for i in range(1700, 2001)], 1850, 300),
            ],
        ],
    )
    def test_apply_roi(self, spectrum, roi, expected):
        """ "
        Runs the same test cases as in test_get_spectrum_from_freq_range(),
        but the desired frequency range is expressed as a proto_cmd.ROIMask object
        """
        spectrum
        result = spectrum.apply_roi(roi)
        assert (result.data == expected.data).all()
        assert result.f_center - expected.f_center < 1e-6
        assert result.span - expected.span < 1e-6

    @pytest.mark.parametrize(
        ["spectrum", "roi"],
        [
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                proto_cmd.ROIMask(center_frequency=6, span=2),
            ],
            [
                Spectrum([101, 102, 103, 104, 105], 10, 4),
                proto_cmd.ROIMask(center_frequency=19, span=0.5),
            ],
            # Test with 1 bin (the span of the returned spectrum will be 0, but a spectrum with 1 bin is not really useful anyway):
            [Spectrum([3.0], 10, 4), proto_cmd.ROIMask(center_frequency=14, span=1)],
            [Spectrum([3.0], 10, 4), proto_cmd.ROIMask(center_frequency=5, span=1)],
            # # 1001 bins from 1000Hz to 2000Hz:
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                proto_cmd.ROIMask(center_frequency=2700, span=2),
            ],
            [
                Spectrum([i for i in range(1000, 2001)], 1500, 1000),
                proto_cmd.ROIMask(center_frequency=2700, span=200),
            ],
        ],
    )
    def test_apply_roi_outside_spectrum(self, spectrum, roi):
        with pytest.raises(IndexError):
            result = spectrum.apply_roi(roi)

    @pytest.mark.parametrize(
        ["freq", "expected"],
        [
            [9, 102],
            [9.8, 103],
        ],
    )
    def test_getitem_freq(self, freq, expected):
        s = Spectrum([101, 102, 103, 104, 105], 10, 4)
        assert s[freq] == expected

    @pytest.mark.parametrize(
        ["f_start", "f_stop", "expected"],
        [
            [8, 11, Spectrum([101, 102, 103, 104], 9.5, 3)],
            [9.8, 11.9, Spectrum([103, 104], 10.5, 1)],
            [9.8, 10.9, Spectrum([103], 10, 1)],
        ],
    )
    def test_getitem_slice(self, f_start, f_stop, expected):
        s = Spectrum([101, 102, 103, 104, 105], 10, 4)
        result = s[f_start:f_stop]
        assert (result.data == expected.data).all()
        assert result.f_center == expected.f_center
        assert result.span == expected.span

    @pytest.mark.parametrize(
        ["roi", "expected"],
        [
            [
                proto_cmd.ROIMask(center_frequency=9.2, span=4),
                Spectrum([101, 102, 103, 104], 9.5, 3),
            ],
            [
                proto_cmd.ROIMask(center_frequency=10.5, span=2),
                Spectrum([103, 104], 10.5, 1),
            ],
            [
                proto_cmd.ROIMask(center_frequency=10.4, span=1.1),
                Spectrum([103], 10, 1),
            ],
        ],
    )
    def test_getitem_roi(self, roi, expected):
        s = Spectrum([101, 102, 103, 104, 105], 10, 4)
        result = s[roi]
        assert (result.data == expected.data).all()
        assert result.f_center == expected.f_center
        assert result.span == expected.span

    @pytest.mark.parametrize(
        "spectrum_array",
        [
            np.array([1, 2, 5, 4, 3]),
        ],
    )
    def test_numpy_array_interface(self, spectrum_array: np.ndarray):
        """Tests some numpy functions if they give the same results on a spectrum as on the data array of the spectrum"""

        s = Spectrum(spectrum_array, 10, 4)

        assert (np.max(s) == np.max(spectrum_array)).all()
        assert (np.argmax(s) == np.argmax(spectrum_array)).all()
        assert (np.exp(s) == np.exp(spectrum_array)).all()
        assert (np.sin(s) == np.sin(spectrum_array)).all()
        assert (np.diag(s) == np.diag(spectrum_array)).all()
        assert (np.max(s) == np.max(spectrum_array)).all()
        assert (np.max(s) == np.max(spectrum_array)).all()
