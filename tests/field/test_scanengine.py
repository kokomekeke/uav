import multiprocessing
from multiprocessing.managers import DictProxy
from queue import Queue
from typing import Any
import pytest

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
from pysagax.field.scanengine import FreqRangeInternal, ScanEngine, ScanEngineState


@pytest.mark.parametrize(
    [
        "fkLH",
        "B",
        "expected_result",
    ],
    [
        [
            (1000, 2000),
            999,
            [
                1250.00,
                1750.00,
            ],
        ],
        [
            (1000, 2000),
            101,
            [
                1050.00,
                1150.00,
                1250.00,
                1350.00,
                1450.00,
                1550.00,
                1650.00,
                1750.00,
                1850.00,
                1950.00,
            ],
        ],
        [
            (1000, 2000),
            123,
            [
                1055.555556,
                1166.666667,
                1277.777778,
                1388.888889,
                1500.000000,
                1611.111111,
                1722.222222,
                1833.333333,
                1944.444444,
            ],
        ],
    ],
)
def test_center_freq_list(fkLH: tuple[float, float], B: float, expected_result):
    fkL, fkH = fkLH
    freq_range = FreqRangeInternal()
    freq_range.start = fkL
    freq_range.stop = fkH
    result = list(freq_range.center_freq_list(B))
    assert len(result) == len(expected_result)
    for res, expected_res in zip(result, expected_result):
        assert res == pytest.approx(expected_res, abs=1e-4)


@pytest.mark.parametrize(
    [
        "useful_bandwidth",
        "freq_ranges",
        "scanning_averaging_burst_count",
        "expected_center_freqs",
    ],
    [
        [
            10e6,
            [(400e6, 440e6), (120e6, 140e6)],
            1,
            [125e6, 135e6, 405e6, 415e6, 425e6, 435e6],
        ],
        [
            10e6,
            [(400e6, 440e6), (120e6, 140e6)],
            2,
            [
                125e6,
                125e6,
                135e6,
                135e6,
                405e6,
                405e6,
                415e6,
                415e6,
                425e6,
                425e6,
                435e6,
                435e6,
            ],
        ],
    ],
)
def test_scan_algorithm(
    useful_bandwidth, freq_ranges, expected_center_freqs, scanning_averaging_burst_count
) -> None:
    """
    Test PPHeadingSync._update_delta_t()
    Params:
        useful_bandwidth: usable bandwidth of one scan burst
        freq_ranges: tuples of start and stop frequencies
        expected_center_freqs: scanning center frequencies, output of scan algorithm
    """
    se = ScanEngine(
        useful_bandwidth, useful_bandwidth, scanning_averaging_burst_count, 1
    )
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

    se = ScanEngine(4000000, 4000000, 1, 1)
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
def test_conf_scanning_state_machine(
    se: ScanEngine, fail_config: bool, fail_scan_start: bool
) -> None:

    assert se._se_commands_q is not None
    assert se._se_responses_q is not None
    assert se._cs_commands_q is not None
    assert se._cs_responses_q is not None
    assert se._post_proc_to_scan_engine_q is not None

    # Initial state
    assert se.state == ScanEngineState.MANUAL

    # ScanEngine Config command
    se_conf_command = proto_cmd.Command()
    se_conf_command.kind = proto_cmd.Command.WRITE
    se_conf_command.instruction = proto_cmd.CONFIG
    se_conf_command.config.se.mode = proto_cmd.ScanEngineConfig.SCANNING
    test_range = se_conf_command.config.se.scanning.ranges.add()
    test_range.start = 440e6
    test_range.stop = 450e6
    se._se_commands_q.put(se_conf_command)

    # Prepare mock CoreService Config Response
    cs_conf_response = proto_cmd.Response()
    if fail_config:
        cs_conf_response.error.description = "Conf failed"
    se._cs_responses_q.put(cs_conf_response)

    # Do FSM loop
    se._loop()

    # Validate command sent to CoreService
    cs_conf_command, _ = se._cs_commands_q.get_nowait()
    assert isinstance(cs_conf_command, proto_cmd.Command)
    assert cs_conf_command.instruction == proto_cmd.CONFIG
    assert cs_conf_command.kind == proto_cmd.Command.WRITE
    assert len(cs_conf_command.config.cs.scan_plan.center_freqs) >= 2

    # Validate response received from ScanEngine
    se_conf_response = se._se_responses_q.get_nowait()
    assert isinstance(se_conf_response, proto_cmd.Response)
    if fail_config:
        assert se.state == ScanEngineState.MANUAL
        assert se_conf_response.error.description
        return
    else:
        assert se.state == ScanEngineState.SCANNING_IDLE
        assert se_conf_response.config.se.scanning.ranges[0] == test_range

    # On the next FSM iteration scanning should start automatically
    # Prepare mock CoreService ScanStart Response
    cs_scan_start_response = proto_cmd.Response()
    if fail_scan_start:
        cs_scan_start_response.error.description = "Scan start failed"
    se._cs_responses_q.put(cs_scan_start_response)
    se._cs_responses_q.put(proto_cmd.Response())

    # Do FSM loop
    se._loop()

    # Validate command sent to CoreService
    cs_scan_start_command, _ = se._cs_commands_q.get_nowait()
    assert isinstance(cs_scan_start_command, proto_cmd.Command)
    assert cs_scan_start_command.instruction == proto_cmd.CS_SCAN_START

    # Validate ScanEngine FSM state
    if fail_scan_start:
        assert se.state == ScanEngineState.SCANNING_IDLE
        return
    else:
        assert se.state == ScanEngineState.SCANNING_IN_PROGRESS

    # Internal variable should now be set to expect postproc data
    expected_burst_count = se._expected_data_count
    assert expected_burst_count > 0

    # Mock postproc data burst packets
    for burst_index in range(expected_burst_count):
        assert se.state == ScanEngineState.SCANNING_IN_PROGRESS
        se._post_proc_to_scan_engine_q.put(proto_data.Measurement())
        se._loop()

    # After all expected postproc packets received,
    # FSM should automatically return to SCANNING_IDLE
    assert se.state == ScanEngineState.SCANNING_IDLE

    # Test return to MANUAL mode
    se_off_command = proto_cmd.Command()
    se_off_command.kind = proto_cmd.Command.WRITE
    se_off_command.instruction = proto_cmd.CONFIG
    se_off_command.config.cs.center_frequency = 100e6
    se._se_commands_q.put(se_off_command)

    # Do FSM loop
    se._loop()

    assert se.state == ScanEngineState.MANUAL


@pytest.mark.parametrize("fail_config", [True, False])
@pytest.mark.parametrize("fail_scan_start", [True, False])
def test_conf_tracking_state_machine(
    se: ScanEngine, fail_config: bool, fail_scan_start: bool
) -> None:

    assert se._se_commands_q is not None
    assert se._se_responses_q is not None
    assert se._cs_commands_q is not None
    assert se._cs_responses_q is not None
    assert se._post_proc_to_scan_engine_q is not None

    # Initial state
    assert se.state == ScanEngineState.MANUAL

    # ScanEngine Config command
    se_conf_command = proto_cmd.Command()
    se_conf_command.kind = proto_cmd.Command.WRITE
    se_conf_command.instruction = proto_cmd.CONFIG
    se_conf_command.config.se.mode = proto_cmd.ScanEngineConfig.TRACKING
    se_conf_command.config.se.tracking.frequency = 446e6
    se_conf_command.config.se.tracking.bandwidth = 2.5e6
    se._se_commands_q.put(se_conf_command)

    # Prepare mock CoreService Config Response
    cs_conf_response = proto_cmd.Response()
    if fail_config:
        cs_conf_response.error.description = "Conf failed"
    se._cs_responses_q.put(cs_conf_response)

    # Do FSM loop
    se._loop()

    # Validate command sent to CoreService
    cs_conf_command, _ = se._cs_commands_q.get_nowait()
    assert isinstance(cs_conf_command, proto_cmd.Command)
    assert cs_conf_command.instruction == proto_cmd.CONFIG
    assert cs_conf_command.kind == proto_cmd.Command.WRITE
    assert cs_conf_command.config.cs.iq_rate == pytest.approx(5.6e6)
    assert cs_conf_command.config.cs.center_frequency == pytest.approx(
        se_conf_command.config.se.tracking.frequency - 2.8e6
    )

    # Validate response received from ScanEngine
    se_conf_response = se._se_responses_q.get_nowait()
    assert isinstance(se_conf_response, proto_cmd.Response)
    if fail_config:
        assert se.state == ScanEngineState.MANUAL
        assert se_conf_response.error.description
        return
    else:
        assert se.state == ScanEngineState.TRACKING_IDLE
        assert se_conf_response.config.se.tracking.frequency == pytest.approx(
            se_conf_command.config.se.tracking.frequency
        )
        assert se_conf_response.config.se.tracking.bandwidth == pytest.approx(
            se_conf_command.config.se.tracking.bandwidth
        )

    # On the next FSM iteration tracking should start automatically
    # Prepare mock CoreService ScanStart Response
    cs_tr_start_response = proto_cmd.Response()
    if fail_scan_start:
        cs_tr_start_response.error.description = "Tr start failed"
    se._cs_responses_q.put(cs_tr_start_response)
    se._cs_responses_q.put(proto_cmd.Response())

    # Do FSM loop
    se._loop()

    # Validate command sent to CoreService
    cs_scan_start_command, _ = se._cs_commands_q.get_nowait()
    assert isinstance(cs_scan_start_command, proto_cmd.Command)
    assert cs_scan_start_command.instruction == proto_cmd.SOURCE_START

    # Validate ScanEngine FSM state
    if fail_scan_start:
        assert se.state == ScanEngineState.TRACKING_IDLE
        return
    else:
        assert se.state == ScanEngineState.TRACKING_IN_PROGRESS

    # On the next FSM iteration no data is yet received,
    # FSM should remain in TRACKING_IN_PROGRESS
    se._loop()
    assert se.state == ScanEngineState.TRACKING_IN_PROGRESS

    # On the next FSM iteration tracking is done
    se._post_proc_to_scan_engine_q.put(proto_data.Measurement())
    se._loop()
    assert se.state == ScanEngineState.TRACKING_IDLE

    # Test return to MANUAL mode
    test_off = proto_cmd.Command()
    test_off.kind = proto_cmd.Command.WRITE
    test_off.instruction = proto_cmd.CONFIG
    test_off.config.cs.center_frequency = 100e6
    se._se_commands_q.put(test_off)
    se._loop()

    assert se.state == ScanEngineState.MANUAL
