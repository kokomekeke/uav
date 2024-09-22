from __future__ import annotations
import logging
from queue import Queue
import queue
import time

from typing import Any, Optional

from pysagax.common.loop import Loop
from pysagax.gnd.uav_report import UAVReport


class Monitoring(Loop):
    """Background process for monitoring UAV status and self check"""

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        self._telemetry_to_monitoring: Optional[Queue] = None
        self.active_warns: set[tuple[int, int]] = set()
        Loop.__init__(self, *args, **kwargs)

    def __call__(
        self,
        telemetry_to_monitoring: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._telemetry_to_monitoring = telemetry_to_monitoring
        return super()._call(*args, **kwargs)

    def _check(
        self,
        uav_id: int,
        uav_identifier_str: str,
        condition: bool,
        check_id: int,
        warn_message: str,
    ) -> None:
        check_tuple = (uav_id, check_id)
        if condition:
            if check_tuple not in self.active_warns:
                self._logger.error(f"{uav_identifier_str}: {warn_message}")
                self.active_warns.add(check_tuple)
            else:
                # this error has been going on for a while...
                pass
        else:
            # problem solved
            self.active_warns.remove(check_tuple)

    def _loop(self) -> None:
        assert self._telemetry_to_monitoring is not None
        time.sleep(1000)
        try:
            while True:
                report = self._telemetry_to_monitoring.get(block=False)
                assert isinstance(report, UAVReport)
                report.evaluate(
                    lambda cond, cid, wstr: self._check(
                        report.uav_id,
                        f"UAV {report.uav_id} ({report.uav_label} on {report.uav_address})",
                        cond,
                        cid,
                        wstr,
                    )
                )
        except queue.Empty:
            pass
