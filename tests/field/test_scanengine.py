import pytest

import pysagax.message.command_pb2 as proto_cmd
from pysagax.field.scanengine import ScanEngine


@pytest.mark.parametrize(
    ["useful_bandwidth", "freq_ranges", "expected_center_freqs"],
    [[2e6, [(430e6, 440e6)], [431e6, 433e6, 435e6, 437e6, 439e6]]],
)
def test_scan_algorithm(useful_bandwidth, freq_ranges, expected_center_freqs):
    """
    Test PPHeadingSync._update_delta_t()
    Params:
        useful_bandwidth: usable bandwidth of one scan burst
        freq_ranges: tuples of start and stop frequencies
        expected_center_freqs: scanning center frequencies, output of scan algorithm
    """
    se = ScanEngine(useful_bandwidth, useful_bandwidth, 1, 1)
    scan_conf = proto_cmd.ScanningConfig()
    for ran in freq_ranges:
        ran_pb = scan_conf.ranges.add()
        ran_pb.start = ran[0]
        ran_pb.stop = ran[1]
    result = se._scan_algorithm(scan_conf)
    assert len(expected_center_freqs) == len(result.center_freqs)
    for expected, actual in zip(expected_center_freqs, result.center_freqs):
        assert actual == pytest.approx(expected)
