import enum
import logging
from multiprocessing.managers import DictProxy
import queue
import time
from queue import Queue
from typing import Any, Generator, Optional, overload

from transitions import Machine
import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
from pysagax.common.loop import Loop


class FreqRangeInternal:
    def __init__(self, freq_range: Optional[proto_cmd.FreqRange] = None) -> None:
        self.start = freq_range.start if freq_range is not None else 0.0
        self.stop = freq_range.stop if freq_range is not None else 0.0

    @property
    def bandwidth(self) -> float:
        return self.stop - self.start

    def overlap(self, other: "FreqRangeInternal") -> bool:
        assert self.start <= self.stop and other.start <= other.stop
        return (
            (self.start <= other.start and other.start <= self.stop)
            or (self.start <= other.stop and other.stop <= self.stop)
            or (other.start < self.start and self.stop < other.stop)
        )

    def merge(self, other: "FreqRangeInternal") -> None:
        if not self.overlap(other):
            return
        if self.stop < other.stop:
            self.stop = other.stop
        if other.start < self.start:
            self.start = other.start

    def center_freq_list(
        self, useful_bandwidth: float, repeat: int = 1
    ) -> Generator[float, None, None]:
        number_of_jumps = -int(-self.bandwidth // useful_bandwidth)  # ceil
        starting_center = (
            self.start
            + (self.bandwidth - useful_bandwidth * number_of_jumps) / 2
            + useful_bandwidth / 2
        )
        for i in range(number_of_jumps):
            freq = starting_center + i * useful_bandwidth
            for _ in range(repeat):
                yield freq
        return None

    def __str__(self) -> str:
        return f"{self.start/1e6:.1f}M-{self.stop/1e6:.1f}M"


class ScanEngineState(enum.Enum):
    MANUAL = 0
    SCANNING_IDLE = 1
    TRACKING_IDLE = 2
    SCANNING_IN_PROGRESS = 3
    TRACKING_IN_PROGRESS = 4


# class PyiMachine(Machine):
#     def generate_pyi(self):
#         with open(f'{__file__}i', 'w') as f:
#             for model in self.models:
#                 f.write(f'class {model.__class__.__name__}:\n')
#                 for event in self.events:
#                     f.write(f'    @overload\n    def {event}(self, *args, **kwargs) -> bool: ...\n')
#                 f.write('\n\n')
#         print(f'{__file__}i generated')


class ScanEngine(Loop):

    @overload
    def switch_scanning(self, *args, **kwargs) -> bool: ...  # type: ignore

    @overload
    def switch_tracking(self, *args, **kwargs) -> bool: ...  # type: ignore

    @overload
    def off(self, *args, **kwargs) -> bool: ...  # type: ignore

    @overload
    def launch(self, *args, **kwargs) -> bool: ...  # type: ignore

    @overload
    def done(self, *args, **kwargs) -> bool: ...  # type: ignore

    """Background process for communicating with the PySAGAX-Heading service"""

    transitions = [
        {
            "trigger": "switch_scanning",
            "source": ScanEngineState.MANUAL,
            "dest": ScanEngineState.SCANNING_IDLE,
            "prepare": "configure_scanning",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "switch_scanning",
            "source": ScanEngineState.TRACKING_IDLE,
            "dest": ScanEngineState.SCANNING_IDLE,
            "prepare": "configure_scanning",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "switch_scanning",
            "source": ScanEngineState.SCANNING_IDLE,
            "dest": ScanEngineState.SCANNING_IDLE,
            "prepare": "configure_scanning",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "switch_tracking",
            "source": ScanEngineState.MANUAL,
            "dest": ScanEngineState.TRACKING_IDLE,
        },
        {
            "trigger": "switch_tracking",
            "source": ScanEngineState.SCANNING_IDLE,
            "dest": ScanEngineState.TRACKING_IDLE,
        },
        {
            "trigger": "off",
            "source": ScanEngineState.TRACKING_IDLE,
            "dest": ScanEngineState.MANUAL,
            "prepare": "configure_manual",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "off",
            "source": ScanEngineState.SCANNING_IDLE,
            "dest": ScanEngineState.MANUAL,
            "prepare": "configure_manual",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "off",
            "source": ScanEngineState.MANUAL,
            "dest": ScanEngineState.MANUAL,
            "prepare": "configure_manual",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "launch",
            "source": ScanEngineState.TRACKING_IDLE,
            "dest": ScanEngineState.TRACKING_IN_PROGRESS,
        },
        {
            "trigger": "launch",
            "source": ScanEngineState.SCANNING_IDLE,
            "dest": ScanEngineState.SCANNING_IN_PROGRESS,
            "prepare": "command_scanning",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "done",
            "source": ScanEngineState.TRACKING_IN_PROGRESS,
            "dest": ScanEngineState.TRACKING_IDLE,
        },
        {
            "trigger": "done",
            "source": ScanEngineState.SCANNING_IN_PROGRESS,
            "dest": ScanEngineState.SCANNING_IDLE,
        },
    ]

    def __init__(
        self,
        # TODO: Define useful defaults
        scanning_iq_rate: int,
        scanning_useful_bandwidth: int,
        scanning_averaging_burst_count: int,
        scanning_target_resolution_bandwidth: int,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        self._iq_rate: int = scanning_iq_rate
        self._useful_bandwidth: int = scanning_useful_bandwidth
        self._averaging_burst_count: int = scanning_averaging_burst_count
        self._target_resolution_bandwidth: int = scanning_target_resolution_bandwidth
        self._cs_commands_q: Optional[Queue] = None
        self._cs_responses_q: Optional[Queue] = None
        self._se_commands_q: Optional[Queue] = None
        self._se_responses_q: Optional[Queue] = None
        self._queue_status: Optional[Queue] = None
        self._post_proc_to_scan_engine_q: Optional[Queue] = None
        self._latest_telemetry_proxy: Optional[DictProxy] = None
        self.state: ScanEngineState = ScanEngineState.MANUAL
        logging.getLogger("transitions").setLevel(self._logger.level)
        self._machine = Machine(
            self,
            states=ScanEngineState,
            transitions=ScanEngine.transitions,
            initial=ScanEngineState.MANUAL,
        )
        self._latest_cs_response: Optional[proto_cmd.Response] = None
        self._configured_freq_ranges: list[FreqRangeInternal] = []
        # self._machine.generate_pyi()
        self._expected_data_count: int = 0
        self._received_data_count: int = 0

    def __call__(
        self,
        cs_commands_q: Queue[Any],
        cs_responses_q: Queue[Any],
        se_commands_q: Queue[Any],
        se_responses_q: Queue[Any],
        post_proc_to_scan_engine_q: Queue[Any],
        latest_telemetry_proxy: DictProxy,
        *args,
        **kwargs,
    ) -> None:
        self._cs_commands_q = cs_commands_q
        self._cs_responses_q = cs_responses_q
        self._se_commands_q = se_commands_q
        self._se_responses_q = se_responses_q
        self._latest_telemetry_proxy = latest_telemetry_proxy
        self._post_proc_to_scan_engine_q = post_proc_to_scan_engine_q
        return super()._call(*args, **kwargs)

    def _scan_algorithm(
        self, scan_conf: proto_cmd.ScanningConfig
    ) -> proto_cmd.FreqList:
        freq_list = proto_cmd.FreqList()
        freq_ranges = sorted(scan_conf.ranges, key=lambda ran: ran.start)
        freq_ranges_united: list[FreqRangeInternal] = [
            FreqRangeInternal(freq_ranges[0])
        ]
        for ran in [FreqRangeInternal(r) for r in freq_ranges[1:]]:
            if ran.overlap(freq_ranges_united[-1]):
                freq_ranges_united[-1].merge(ran)
            else:
                freq_ranges_united.append(ran)
        freq_list.iq_rate = self._iq_rate
        for ran in freq_ranges_united:
            freq_list.center_freqs.extend(
                ran.center_freq_list(
                    self._useful_bandwidth, repeat=self._averaging_burst_count
                )
            )
        self._configured_freq_ranges = freq_ranges_united
        self._expected_data_count = len(freq_list.center_freqs)
        self._received_data_count = 0
        self._logger.info(
            f"Scan algorithm finished for ranges {', '.join(str(f) for f in freq_ranges_united)}"
        )
        return freq_list

    def check_cs_response(self) -> bool:
        assert self._cs_responses_q is not None
        response: proto_cmd.Response = self._cs_responses_q.get()
        self._latest_cs_response = response
        return not response.HasField("error")

    def configure_scanning(self, scan_cmd: proto_cmd.Command) -> None:
        assert self._cs_commands_q is not None
        command = proto_cmd.Command()
        command.instruction = proto_cmd.CONFIG
        command.config.cs.scan_plan.CopyFrom(
            self._scan_algorithm(scan_cmd.config.se.scanning)
        )
        self._cs_commands_q.put(command)

    def configure_tracking(self, track_cmd: proto_cmd.Command) -> None:
        pass

    def configure_manual(self, manual_cmd: proto_cmd.Command) -> None:
        assert self._cs_commands_q is not None
        self._cs_commands_q.put(manual_cmd)

    def command_scanning(self):
        command = proto_cmd.Command()
        command.instruction = proto_cmd.CS_SCAN_START

    def construct_config_report(self) -> proto_cmd.ScanEngineConfig:
        se_config = proto_cmd.ScanEngineConfig()

        se_config.mode = {
            ScanEngineState.MANUAL: proto_cmd.ScanEngineConfig.MANUAL,
            ScanEngineState.SCANNING_IDLE: proto_cmd.ScanEngineConfig.SCANNING,
            ScanEngineState.SCANNING_IN_PROGRESS: proto_cmd.ScanEngineConfig.SCANNING,
            ScanEngineState.TRACKING_IDLE: proto_cmd.ScanEngineConfig.TRACKING,
            ScanEngineState.TRACKING_IN_PROGRESS: proto_cmd.ScanEngineConfig.TRACKING,
        }[self.state]
        if se_config.mode == proto_cmd.ScanEngineConfig.SCANNING:
            for ran in self._configured_freq_ranges:
                pb_ran = se_config.scanning.ranges.add()
                pb_ran.start = ran.start
                pb_ran.stop = ran.stop
        return se_config

    def _pre_loop(self) -> None:
        self._logger.info("ScanEngine starts")

    def _handle_incoming_instruction(self, timeout: float) -> bool:
        assert self._se_commands_q is not None and self._se_responses_q is not None
        try:
            command: proto_cmd.Command = self._se_commands_q.get(timeout=timeout)
        except queue.Empty:
            return False
        if (
            command.instruction == proto_cmd.CONFIG
            and command.kind == proto_cmd.Command.WRITE
        ):
            if command.config.HasField("se") and command.config.se.mode in [
                proto_cmd.ScanEngineConfig.SCANNING,
                proto_cmd.ScanEngineConfig.TRACKING,
            ]:
                if command.config.se.mode == proto_cmd.ScanEngineConfig.SCANNING:
                    self.switch_scanning(scan_cmd=command.config.se.scanning)
                elif command.config.se.mode == proto_cmd.ScanEngineConfig.TRACKING:
                    self.switch_tracking(track_cmd=command.config.se.tracking)
                response = proto_cmd.Response()
                response.config.se.CopyFrom(self.construct_config_report())
                self._se_responses_q.put(response)
            else:
                self.off(manual_cmd=command)
                assert self._latest_cs_response is not None
                self._se_responses_q.put(self._latest_cs_response)
                self._latest_cs_response = None
        return True

    def _discard_post_proc_output(self) -> None:
        assert self._post_proc_to_scan_engine_q is not None
        try:
            while True:
                self._post_proc_to_scan_engine_q.get_nowait()
        except queue.Empty:
            pass

    def _loop(self) -> None:
        q_timeout = 1
        assert (
            self._cs_commands_q is not None
            and self._cs_responses_q is not None
            and self._se_commands_q is not None
            and self._se_responses_q is not None
            and self._post_proc_to_scan_engine_q is not None
            and self._latest_telemetry_proxy is not None
        )
        match self.state:
            case ScanEngineState.MANUAL:
                self._discard_post_proc_output()
                self._handle_incoming_instruction(q_timeout)
            case ScanEngineState.SCANNING_IDLE:
                self._discard_post_proc_output()
                if not self._handle_incoming_instruction(q_timeout):
                    self.launch()
            case ScanEngineState.TRACKING_IDLE:
                self._discard_post_proc_output()
                if not self._handle_incoming_instruction(0.0):
                    self.launch()
            case ScanEngineState.SCANNING_IN_PROGRESS:
                try:
                    post_proc_data: proto_data.Measurement = (
                        self._post_proc_to_scan_engine_q.get(timeout=q_timeout)
                    )
                    self._received_data_count += 1
                    if self._received_data_count == self._expected_data_count:
                        self.done()
                        self._logger.info(
                            f"Scan finished, received {self._received_data_count} bursts"
                        )

                except queue.Empty:
                    self._logger.error(
                        f"Scan mode timed out, received {self._received_data_count} of {self._expected_data_count} bursts"
                    )
                    self.done()
            case ScanEngineState.TRACKING_IN_PROGRESS:
                try:
                    post_proc_data: proto_data.Measurement = (
                        self._post_proc_to_scan_engine_q.get(timeout=q_timeout)
                    )
                    # TODO adjust params
                except queue.Empty:
                    self._logger.error(f"Tracking mode timed out")
                    self.done()
