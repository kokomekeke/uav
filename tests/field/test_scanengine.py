import multiprocessing
from multiprocessing.managers import DictProxy
from queue import Queue
from typing import Any
import pytest

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
from pysagax.field.scanengine import ScanEngine, ScanEngineState


@pytest.mark.parametrize(
    ["useful_bandwidth", "freq_ranges", "expected_center_freqs"],
    [[2e6, [(430e6, 440e6)], [431e6, 433e6, 435e6, 437e6, 439e6]]],
)
def test_scan_algorithm(useful_bandwidth, freq_ranges, expected_center_freqs) -> None:
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

@pytest.fixture
def se() -> ScanEngine:

    se = ScanEngine(2000000, 2000000, 1, 1)
    se._cs_commands_q = Queue()
    se._cs_responses_q = Queue()
    se._se_commands_q = Queue()
    se._se_responses_q = Queue()
    se._post_proc_to_scan_engine_q = Queue()
    se._latest_telemetry_proxy = multiprocessing.Manager().dict()
    se._pre_loop()
    return se


@pytest.mark.parametrize("fail_config", [True, False])
@pytest.mark.parametrize("fail_scan_start", [True, False])
def test_conf_scanning_state_machine(se: ScanEngine, fail_config: bool, fail_scan_start: bool) -> None:

    assert se._se_commands_q is not None
    assert se._cs_responses_q is not None
    assert se._post_proc_to_scan_engine_q is not None

    test_cmd = proto_cmd.Command()
    
    assert(se.state == ScanEngineState.MANUAL)

    test_cmd.kind = proto_cmd.Command.WRITE
    test_cmd.instruction = proto_cmd.CONFIG
    test_cmd.config.se.mode = proto_cmd.ScanEngineConfig.SCANNING
    test_range = test_cmd.config.se.scanning.ranges.add()
    test_range.start = 440e6
    test_range.stop = 450e6
    se._se_commands_q.put(test_cmd)
    print(test_cmd)
    conf_resp = proto_cmd.Response()
    if fail_config:
        conf_resp.error.description = "Conf failed"
    se._cs_responses_q.put(conf_resp)
    se._loop()
    if fail_config:
        assert(se.state == ScanEngineState.MANUAL)
        return
    else:
        assert(se.state == ScanEngineState.SCANNING_IDLE)
    scan_start_resp = proto_cmd.Response()
    if fail_scan_start:
        scan_start_resp.error.description = "Scan start failed"
    se._cs_responses_q.put(scan_start_resp)
    se._cs_responses_q.put(proto_cmd.Response())
    se._loop()
    if fail_scan_start:
        assert(se.state == ScanEngineState.SCANNING_IDLE)
        return
    else:
        assert(se.state == ScanEngineState.SCANNING_IN_PROGRESS)
    expected_burst_count = se._expected_data_count
     
    for burst_index in range(expected_burst_count):
        print(burst_index)
        assert(se.state == ScanEngineState.SCANNING_IN_PROGRESS)
        se._post_proc_to_scan_engine_q.put(proto_data.Measurement())
        se._loop()

    assert(se.state == ScanEngineState.SCANNING_IDLE)

