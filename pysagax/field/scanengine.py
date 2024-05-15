import enum
import logging
from multiprocessing.managers import DictProxy
import queue
import time
from queue import Queue
from typing import Any, Optional, overload

from transitions import Machine
import pysagax.message.heading_pb2 as proto_heading
from pysagax.common.loop import Loop
from pysagax.communication.pub_sub import SUB
from pysagax.communication.req_rep_tcp import REQ


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
    def start_scanning(self, *args, **kwargs) -> bool: ...  # type: ignore

    @overload
    def start_tracking(self, *args, **kwargs) -> bool: ...  # type: ignore

    @overload
    def off(self, *args, **kwargs) -> bool: ...  # type: ignore

    @overload
    def working(self, *args, **kwargs) -> bool: ...  # type: ignore

    @overload
    def done(self, *args, **kwargs) -> bool: ...  # type: ignore

    """Background process for communicating with the PySAGAX-Heading service"""

    transitions = [
        ["start_scanning", ScanEngineState.MANUAL, ScanEngineState.SCANNING_IDLE],
        [
            "start_scanning",
            ScanEngineState.TRACKING_IDLE,
            ScanEngineState.SCANNING_IDLE,
        ],
        ["start_tracking", ScanEngineState.MANUAL, ScanEngineState.TRACKING_IDLE],
        [
            "start_tracking",
            ScanEngineState.SCANNING_IDLE,
            ScanEngineState.TRACKING_IDLE,
        ],
        ["off", ScanEngineState.TRACKING_IDLE, ScanEngineState.MANUAL],
        ["off", ScanEngineState.SCANNING_IDLE, ScanEngineState.MANUAL],
        [
            "working",
            ScanEngineState.TRACKING_IDLE,
            ScanEngineState.TRACKING_IN_PROGRESS,
        ],
        [
            "working",
            ScanEngineState.SCANNING_IDLE,
            ScanEngineState.SCANNING_IN_PROGRESS,
        ],
        ["done", ScanEngineState.TRACKING_IN_PROGRESS, ScanEngineState.TRACKING_IDLE],
        ["done", ScanEngineState.SCANNING_IN_PROGRESS, ScanEngineState.SCANNING_IDLE],
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
        self._latest_postproc_status: Optional[DictProxy] = None
        self.state: ScanEngineState = ScanEngineState.MANUAL
        self._machine = Machine(
            self,
            states=ScanEngineState,
            transitions=ScanEngine.transitions,
            initial=ScanEngineState.MANUAL,
        )
        # self._machine.generate_pyi()

    def __call__(
        self,
        cs_commands_q: Queue[Any],
        cs_responses_q: Queue[Any],
        se_commands_q: Queue[Any],
        se_responses_q: Queue[Any],
        latest_postproc_status: DictProxy,
        *args,
        **kwargs,
    ) -> None:
        self._cs_commands_q = cs_commands_q
        self._cs_responses_q = cs_responses_q
        self._se_commands_q = se_commands_q
        self._se_responses_q = se_responses_q
        self._latest_postproc_status = latest_postproc_status
        return super()._call(*args, **kwargs)

    def _pre_loop(self) -> None:
        self._logger.info("ScanEngine starts")

    def _loop(self) -> None:

        assert (
            self._cs_commands_q is not None
            and self._cs_responses_q is not None
            and self._se_commands_q is not None
            and self._se_responses_q is not None
            and self._latest_postproc_status is not None
        )
        print(self.state)
        self.start_tracking()
        time.sleep(1)
