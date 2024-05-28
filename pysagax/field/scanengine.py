import enum
import logging
from multiprocessing.managers import DictProxy
import queue
from queue import Queue
from typing import Any, Generator, Optional, overload

from transitions import Machine
import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
from pysagax.common.loop import Loop


class FreqRangeInternal:
    """
    Helper class for storing start and stop frequencies on frequency ranges,
    and calculating frequency hopping on it. It is only to be used by ScanEngine.
    """

    def __init__(self, freq_range: Optional[proto_cmd.FreqRange] = None) -> None:
        self.start = freq_range.start if freq_range is not None else 0.0
        self.stop = freq_range.stop if freq_range is not None else 0.0

    @property
    def bandwidth(self) -> float:
        return self.stop - self.start

    def overlap(self, other: "FreqRangeInternal") -> bool:
        """
        Returns: True if two frequency ranges overlap
        """
        assert self.start <= self.stop and other.start <= other.stop
        return (
            (self.start <= other.start and other.start <= self.stop)
            or (self.start <= other.stop and other.stop <= self.stop)
            or (other.start < self.start and self.stop < other.stop)
        )

    def merge(self, other: "FreqRangeInternal") -> None:
        """
        Merges other range into this one by extending the boundaries of this one.
        """
        if not self.overlap(other):
            return
        if self.stop < other.stop:
            self.stop = other.stop
        if other.start < self.start:
            self.start = other.start

    def center_freq_list(
        self, useful_bandwidth: float, repeat: int = 1
    ) -> Generator[float, None, None]:
        """
        Generates center frequency list based on scan algorithm.
        https://sagaxcommunications.atlassian.net/wiki/spaces/ALTS/pages/245071917/Scan+Engine#Scan-algoritmus
        """
        number_of_jumps = -int(-self.bandwidth // useful_bandwidth)  # ceil
        jump_bandwidth = self.bandwidth / float(number_of_jumps)
        for i in range(number_of_jumps):
            freq = self.start + (i + 0.5) * jump_bandwidth
            for _ in range(repeat):
                yield freq
        return None

    def __str__(self) -> str:
        return f"{self.start/1e6:.1f}M-{self.stop/1e6:.1f}M"


class ScanEngineState(enum.Enum):
    INIT = 0
    MANUAL = 1
    SCANNING_IDLE = 2
    TRACKING_IDLE = 3
    SCANNING_IN_PROGRESS = 4
    TRACKING_IN_PROGRESS = 5


class StateMachine(Machine):

    def _checked_assignment(self, model, name, func):
        """
        This allows method overriding in pytransitions, so that
        we can define FSM transition methods in advance and make
        linters understand FSM trigger calls.
        """
        setattr(model, name, func)


class ScanEngine(Loop):
    """FSM transition triggers"""

    @overload
    def initialize(self, *args, **kwargs) -> bool: ...  # type: ignore

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

    """ FSM transitions """
    transitions = [
        {
            "trigger": "initialize",
            "source": ScanEngineState.INIT,
            "dest": ScanEngineState.MANUAL,
            "prepare": "query_cs_config",
            "conditions": "check_cs_response",
        },
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
            "prepare": "configure_tracking",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "switch_tracking",
            "source": ScanEngineState.SCANNING_IDLE,
            "dest": ScanEngineState.TRACKING_IDLE,
            "prepare": "configure_tracking",
            "conditions": "check_cs_response",
        },
        {
            "trigger": "switch_tracking",
            "source": ScanEngineState.TRACKING_IDLE,
            "dest": ScanEngineState.TRACKING_IDLE,
            "prepare": "configure_tracking",
            "conditions": "check_cs_response",
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
            "prepare": "command_tracking",
            "conditions": "check_cs_response",
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

    """ The IQ rate list of the Sidekiq radios    """
    supported_iq_rates = [
        541667,
        1920000,
        2457600,
        2800000,
        3840000,
        4000000,
        4915200,
        5600000,
        7680000,
        9830400,
        10000000,
        11200000,
        15360000,
        16000000,
        20000000,
        21666700,
        22000000,
        23040000,
        30720000,
        40000000,
        61440000,
    ]

    def __init__(
        self,
        scanning_iq_rate: int,
        scanning_useful_bandwidth: int,
        scanning_averaging_burst_count: int,
        scanning_target_resolution_bandwidth: int,
        timeout_config_ms: int = 30000,
        timeout_instruction_ms: int = 1000,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        self._useful_bandwidth_ratio: float = float(scanning_useful_bandwidth) / float(
            scanning_iq_rate
        )
        if scanning_iq_rate not in ScanEngine.supported_iq_rates:
            self._iq_rate = self.to_supported_iq_rate(scanning_iq_rate)
            self._useful_bandwidth: int = int(
                self._iq_rate * self._useful_bandwidth_ratio
            )
            self._logger.warn(
                f"IQ rate {scanning_iq_rate} not supported, using {self._iq_rate} (useful bw {self._useful_bandwidth}"
            )
        else:
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
        self._latest_se_proxy: Optional[DictProxy] = None
        self.state: ScanEngineState = ScanEngineState.INIT
        logging.getLogger("transitions").setLevel(self._logger.level)
        self._machine = StateMachine(
            self,
            states=ScanEngineState,
            transitions=ScanEngine.transitions,
            initial=ScanEngineState.INIT,
        )
        self._latest_cs_response: Optional[proto_cmd.Response] = None
        self._configured_freq_ranges: list[FreqRangeInternal] = []
        self._configured_tracking_frequency = 0.0
        self._configured_tracking_bandwidth = 0.0
        # self._machine.generate_pyi()
        self._expected_data_count: int = 0
        self._received_data_count: int = 0
        self._config_cs_timeout = timeout_config_ms
        self._instruction_cs_timeout = timeout_instruction_ms

    def to_supported_iq_rate(self, iq: int) -> int:
        """
        This is important for certain SDR radios which support a limited set of IQ rates.
        Returns the nearest higher IQ rate from the supported list.
        """
        for rate in ScanEngine.supported_iq_rates:
            if rate >= iq:
                return rate
        return ScanEngine.supported_iq_rates[-1]

    def __call__(
        self,
        cs_commands_q: Queue[Any],
        cs_responses_q: Queue[Any],
        se_commands_q: Queue[Any],
        se_responses_q: Queue[Any],
        post_proc_to_scan_engine_q: Queue[Any],
        latest_se_proxy: DictProxy,
        latest_telemetry_proxy: DictProxy,
        *args,
        **kwargs,
    ) -> None:
        self._cs_commands_q = cs_commands_q
        self._cs_responses_q = cs_responses_q
        self._se_commands_q = se_commands_q
        self._se_responses_q = se_responses_q
        self._latest_se_proxy = latest_se_proxy
        self._latest_telemetry_proxy = latest_telemetry_proxy
        self._post_proc_to_scan_engine_q = post_proc_to_scan_engine_q
        return super()._call(*args, **kwargs)

    def _scan_algorithm(
        self, scan_conf: proto_cmd.ScanningConfig
    ) -> proto_cmd.FreqList:
        """
        Runs the Scan algorithm on the provided scan_conf configuration and
        returns the frequency list needed by CoreService.
        See https://sagaxcommunications.atlassian.net/wiki/spaces/ALTS/pages/245071917/Scan+Engine#Scan-algoritmus
        """
        freq_list = proto_cmd.FreqList()
        if not scan_conf.ranges:
            self._logger.warning("No scan ranges defined!")
            return freq_list
        freq_ranges = sorted(scan_conf.ranges, key=lambda ran: ran.start)
        freq_ranges_united: list[FreqRangeInternal] = [
            FreqRangeInternal(freq_ranges[0])
        ]
        for ran in [FreqRangeInternal(r) for r in freq_ranges[1:]]:
            if ran.overlap(freq_ranges_united[-1]):
                freq_ranges_united[-1].merge(ran)
            else:
                freq_ranges_united.append(ran)
        freq_list.iq_rate = int(self._iq_rate)
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

    def check_cs_response(self, se_cmd: Optional[proto_cmd.Command] = None) -> bool:
        """
        Runs before entering an FSM state, which needs CoreService configuration.
        This is executed after sending a configuration command, and prevents FSM transition
        if an error occurs.
        """
        assert self._cs_responses_q is not None
        response: proto_cmd.Response = self._cs_responses_q.get()
        self._latest_cs_response = response
        if response.HasField("config"):
            if self._latest_se_proxy is not None:
                self._latest_se_proxy["cs_config"] = response.config.cs
        return not response.HasField("error")

    def query_cs_config(self) -> None:
        """
        Action on the INIT -> MANUAL transition.
        Queries the initial configuration of CoreService.
        """
        assert self._cs_commands_q is not None
        command = proto_cmd.Command()
        command.instruction = proto_cmd.CONFIG
        command.kind = proto_cmd.Command.READ
        self._cs_commands_q.put((command, self._instruction_cs_timeout))

    def configure_scanning(self, se_cmd: proto_cmd.Command) -> None:
        """
        Action before entering SCANNING_IDLE state.
        Sends Scanning configuration to CoreService.
        """
        assert self._cs_commands_q is not None
        command = proto_cmd.Command()
        command.instruction = proto_cmd.CONFIG
        command.kind = proto_cmd.Command.WRITE
        command.config.cs.scan_plan.CopyFrom(
            self._scan_algorithm(se_cmd.config.se.scanning)
        )
        self._cs_commands_q.put((command, self._config_cs_timeout))

    def configure_tracking(self, se_cmd: proto_cmd.Command) -> None:
        """
        Action before entering TRACKING_IDLE state.
        Sends Tracking configuration to CoreService.
        """
        assert self._cs_commands_q is not None
        command = proto_cmd.Command()
        command.instruction = proto_cmd.CONFIG
        command.kind = proto_cmd.Command.WRITE

        tracking_bw = self.to_supported_iq_rate(
            int(se_cmd.config.se.tracking.bandwidth / self._useful_bandwidth_ratio) * 2
        )

        # Do not switch to lower IQ rate for tracking, only higher if needed
        command.config.cs.iq_rate = max(tracking_bw, self._iq_rate)

        # Tracked signal should be on the center of the positive side
        # of the baseband signal
        command.config.cs.center_frequency = (
            se_cmd.config.se.tracking.frequency - command.config.cs.iq_rate / 4
        )

        self._configured_tracking_frequency = se_cmd.config.se.tracking.frequency
        self._configured_tracking_bandwidth = se_cmd.config.se.tracking.bandwidth
        self._cs_commands_q.put((command, self._config_cs_timeout))

    def configure_manual(self, se_cmd: proto_cmd.Command) -> None:
        assert self._cs_commands_q is not None

        cs_command = proto_cmd.Command()
        cs_command.CopyFrom(se_cmd)
        cs_command.kind = proto_cmd.Command.WRITE
        if cs_command.HasField("config"):
            cs_command.config.Clear()
            cs_command.config.cs.CopyFrom(se_cmd.config.cs)
        self._cs_commands_q.put((cs_command, self._config_cs_timeout))

    def manual_command(self, cs_command: proto_cmd.Command) -> None:
        """
        Called when a CoreService command arrives on the ScanEngine incoming queue.
        Forwards the message to the CoreService.
        """
        assert self._cs_commands_q is not None
        self._cs_commands_q.put((cs_command, self._instruction_cs_timeout))

    def command_scanning(self):
        """
        Action on the SCANNING_IDLE -> SCANNING_IN_PROGRESS transition.
        Sends the CS_SCAN_START command to CoreService.
        """
        assert self._cs_commands_q is not None
        command = proto_cmd.Command()
        command.instruction = proto_cmd.CS_SCAN_START
        self._cs_commands_q.put((command, self._instruction_cs_timeout))

    def command_tracking(self):
        """
        Action on the TRACKING_IDLE -> TRACKING_IN_PROGRESS transition.
        Sends the SOURCE_START command to CoreService.
        """
        assert self._cs_commands_q is not None
        command = proto_cmd.Command()
        command.instruction = proto_cmd.SOURCE_START
        self._cs_commands_q.put((command, self._instruction_cs_timeout))

    def construct_config_report(self) -> proto_cmd.ScanEngineConfig:
        """
        Called on configuration change. This method constructs the Config report
        which can be queried with the CONFIG READ protobuf command.
        """
        se_config = proto_cmd.ScanEngineConfig()

        se_config.mode = {
            ScanEngineState.INIT: proto_cmd.ScanEngineConfig.MANUAL,
            ScanEngineState.MANUAL: proto_cmd.ScanEngineConfig.MANUAL,
            ScanEngineState.SCANNING_IDLE: proto_cmd.ScanEngineConfig.SCANNING,
            ScanEngineState.SCANNING_IN_PROGRESS: proto_cmd.ScanEngineConfig.SCANNING,
            ScanEngineState.TRACKING_IDLE: proto_cmd.ScanEngineConfig.TRACKING,
            ScanEngineState.TRACKING_IN_PROGRESS: proto_cmd.ScanEngineConfig.TRACKING,
        }[self.state]
        if se_config.mode == proto_cmd.ScanEngineConfig.TRACKING:
            se_config.tracking.frequency = self._configured_tracking_frequency
            se_config.tracking.bandwidth = self._configured_tracking_bandwidth
        if se_config.mode == proto_cmd.ScanEngineConfig.SCANNING:
            for ran in self._configured_freq_ranges:
                pb_ran = se_config.scanning.ranges.add()
                pb_ran.start = ran.start
                pb_ran.stop = ran.stop
        if self._latest_se_proxy is not None:
            self._latest_se_proxy["config"] = se_config
        return se_config

    def _pre_loop(self) -> None:
        self._logger.info("ScanEngine starts")

    def _handle_incoming_instruction(self, timeout: float) -> bool:
        """
        Runs when the FSM is inside a state and allows for an incoming ScanEngine command.
        Returns True if there was an incoming command to process.
        """
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
                self._logger.info(f"ScanEngine configuration {command.config.se.mode}")
                if command.config.se.mode == proto_cmd.ScanEngineConfig.SCANNING:
                    self.switch_scanning(se_cmd=command)
                elif command.config.se.mode == proto_cmd.ScanEngineConfig.TRACKING:
                    self.switch_tracking(se_cmd=command)
                assert self._latest_cs_response is not None
                response = proto_cmd.Response()
                if self._latest_cs_response.HasField("error"):
                    response.error.CopyFrom(self._latest_cs_response.error)
                else:
                    response.config.se.CopyFrom(self.construct_config_report())
                self._protobuf_to_log(response, "ScanEngine conf finished: {}")
                self._se_responses_q.put(response)
                self._latest_cs_response = None
            else:
                self._logger.info(f"ScanEngine manual configuration")
                self.off(se_cmd=command)
                assert self._latest_cs_response is not None
                self._protobuf_to_log(
                    self._latest_cs_response, "Manual conf finished: {}"
                )
                self._se_responses_q.put(self._latest_cs_response)
                self._latest_cs_response = None
        elif (
            command.instruction == proto_cmd.CONFIG
            and command.kind == proto_cmd.Command.READ
        ):
            response = proto_cmd.Response()
            response.config.se.CopyFrom(self.construct_config_report())
            self._se_responses_q.put(response)
        elif command.instruction in [
            proto_cmd.SOURCE_START,
            proto_cmd.SOURCE_STOP,
            proto_cmd.REC_START,
            proto_cmd.REC_STOP,
            proto_cmd.CS_PING,
            proto_cmd.POSITION,
        ]:
            self.manual_command(command)
            self.check_cs_response()
            self._se_responses_q.put(self._latest_cs_response)
        else:
            response = proto_cmd.Response()
            response.error.description = "Unsupported {str(command.instruction)}"
            self._se_responses_q.put(response)
        return True

    def _discard_post_proc_output(self) -> None:
        """
        If the FSM is in such a state that the post proc data is not processed,
        the queue should be emptied.
        """
        assert self._post_proc_to_scan_engine_q is not None
        try:
            while True:
                self._post_proc_to_scan_engine_q.get_nowait()
        except queue.Empty:
            pass

    def _loop(self) -> None:
        q_timeout = 0.5
        assert (
            self._cs_commands_q is not None
            and self._cs_responses_q is not None
            and self._se_commands_q is not None
            and self._se_responses_q is not None
            and self._post_proc_to_scan_engine_q is not None
            and self._latest_telemetry_proxy is not None
        )
        if self._latest_se_proxy is not None:
            # This will be used in the telemetry packet.
            self._latest_se_proxy["state"] = str(self.state).split(".")[-1]

        match self.state:
            case ScanEngineState.INIT:
                self.initialize()
            case ScanEngineState.MANUAL:
                self._discard_post_proc_output()
                # MANUAL mode command handling needs a timeout, because there is no other
                # action in this state and would spin the _loop function very quickly when
                # there are no incoming commands.
                self._handle_incoming_instruction(q_timeout)
            case ScanEngineState.SCANNING_IDLE:
                self._discard_post_proc_output()
                # Timeout is zero, only handle commands that are in the queue right now
                if not self._handle_incoming_instruction(0.0):
                    # If there was an incoming command, the _loop iteration will be used
                    # to execute that command. Only go to the SCANNING_IN_PROGRESS state,
                    # if there aren't any commands left in the queue.
                    self.launch()
            case ScanEngineState.TRACKING_IDLE:
                self._discard_post_proc_output()
                if not self._handle_incoming_instruction(0.0):
                    self.launch()
            case ScanEngineState.SCANNING_IN_PROGRESS:
                try:
                    # Scanning in progress: no commands allowed, the FSM is waiting
                    # for all the Measurement packets to arrive.
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
                    self.done()
                    # TODO adjust params
                except queue.Empty:
                    self._logger.error(f"Tracking mode timed out")
                    self.done()
