import pytest
from pysagax.field.ppstreamprep import PPStreamPreparation
import pysagax.message.data_pb2 as proto_data

import numpy as np
from pysagax.util.protobuf_spectrum_utils import (
    convert_iterable_to_spectrum_data,
    protobuf_spectrum_to_numpy,
)


@pytest.mark.parametrize(
    ["spectrum_data_count", "spectrum_data_type"],
    [
        [[1000], proto_data.Spectrum.DataType.FLOAT32],
        [[4000], proto_data.Spectrum.DataType.FLOAT32],
        [[4000, 4000, 4000], proto_data.Spectrum.DataType.FLOAT16],
        [[4000, 4000, 4000], proto_data.Spectrum.DataType.FLOAT32],
        [[4000, 4000, 4000], proto_data.Spectrum.DataType.INT16],
        [[4000, 4000, 4000], proto_data.Spectrum.DataType.INT8],
    ],
)
def test_calculate_decim_factor(spectrum_data_count, spectrum_data_type):
    packet = proto_data.Measurement()
    for one_count in spectrum_data_count:
        packet_spectrum = packet.data.add()
        packet_spectrum.data_type = spectrum_data_type
        packet_spectrum.data = convert_iterable_to_spectrum_data(
            np.ones(one_count), packet_spectrum.data_type
        )
    pp_streamprep = PPStreamPreparation()
    pp_streamprep._udp_max_size = 8000
    decim = pp_streamprep._calculate_decim_factor(packet)
    packet_test = proto_data.Measurement()
    for one_count in spectrum_data_count:
        packet_spectrum = packet_test.data.add()
        packet_spectrum.data_type = spectrum_data_type
        packet_spectrum.data = convert_iterable_to_spectrum_data(
            np.ones(one_count // decim), packet_spectrum.data_type
        )
    packet_test_size = len(packet_test.SerializeToString())
    assert packet_test_size > pp_streamprep._udp_max_size // 2
    assert packet_test_size < pp_streamprep._udp_max_size


@pytest.mark.parametrize(
    ["original", "decim_factor", "expected"],
    [
        [[1, 2, 3, 4], 1, [1, 2, 3, 4]],
        [[1, 2, 3, 4, 5, 6, 7, 8, 9], 3, [3, 6, 9]],
        [[10, 20, 30, 40, 50], 3, [30, 50]],
        [[10, 20, 30, 40, 50, 60, 70, 80, 90], 4, [40, 80, 90]],
    ],
)
def test_shrink_measurement_packet(original, decim_factor, expected):
    packet = proto_data.Measurement()
    packet_spectrum = packet.data.add()
    packet_spectrum.data_type = proto_data.Spectrum.DataType.INT16
    packet_spectrum.data = convert_iterable_to_spectrum_data(
        original, packet_spectrum.data_type
    )
    pp_streamprep = PPStreamPreparation()
    packet = pp_streamprep._shrink_measurement_packet(packet, decim_factor)

    result = protobuf_spectrum_to_numpy(packet_spectrum)
    assert len(result) == len(expected)
    for actual, expect in zip(result, expected):
        assert actual == expect
