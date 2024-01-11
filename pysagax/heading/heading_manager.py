from __future__ import annotations

import multiprocessing
import multiprocessing.managers
import queue
from typing import Any, Optional, Type

from pysagax.heading.heading_sources import (
    HeadingAHRS,
    HeadingAHRSUSB,
    HeadingAHRSFTDI,
    HeadingEncoder,
    HeadingSource,
    HeadingStatic,
)


class ValueCollector:
    def __init__(self, mp_values: multiprocessing.Queue[tuple[str, Any]]) -> None:
        self.mp_values = mp_values

    def gps_callback(self, lat: float, lon: float) -> None:
        self.mp_values.put(("gps", (lat, lon)))

    def quaternion_callback(self, q0: float, q1: float, q2: float, q3: float) -> None:
        self.mp_values.put(("quaternion", [q0, q1, q2, q3]))

    def invalid_callback(self) -> None:
        self.mp_values.put(("gps", None))
        self.mp_values.put(("quaternion", None))


class StatusCallback:
    def __init__(self, mp_status: multiprocessing.Queue[str]) -> None:
        self.mp_status = mp_status

    def callback(self, status: str) -> None:
        self.mp_status.put(status)


def HeadingWorker(
    heading_source: HeadingSource,
    mp_commands: multiprocessing.Queue[Any],
    mp_status: multiprocessing.Queue[str],
    mp_disconnect: multiprocessing.managers.ValueProxy[int],
    mp_values: multiprocessing.Queue[tuple[str, Any]],
) -> None:
    value_collector = ValueCollector(mp_values)
    status_callback = StatusCallback(mp_status)
    heading_source.gps_updated_callback = value_collector.gps_callback
    heading_source.quaternion_updated_callback = value_collector.quaternion_callback
    heading_source.data_invalid_callback = value_collector.invalid_callback
    heading_source.status_updates_callback = status_callback.callback
    value_collector.invalid_callback()
    initialized: bool = False
    while True:
        try:
            if mp_disconnect.get():
                break
        except TypeError as e:  # TODO: multiprocessing debug (JIRA issue ALTS-150)
            pass
        try:
            while True:
                command = mp_commands.get_nowait()
                if isinstance(command, str):
                    if command == "close":
                        heading_source.close()
                        initialized = False
                    elif command == "initialize":
                        initialized = heading_source.initialize()
                        mp_status.put(
                            f"#compass{str(heading_source.__class__.__name__)}"
                        )
                elif isinstance(command, tuple):
                    heading_source.update_parameter(command[0], command[1])
                elif isinstance(command, HeadingSource):
                    heading_source.close()
                    initialized = False
                    heading_source = command
                    heading_source.gps_updated_callback = value_collector.gps_callback
                    heading_source.quaternion_updated_callback = (
                        value_collector.quaternion_callback
                    )
                    heading_source.data_invalid_callback = (
                        value_collector.invalid_callback
                    )
                    heading_source.status_updates_callback = status_callback.callback
                    value_collector.invalid_callback()
        except queue.Empty:
            pass
        if initialized:
            heading_source.loop()
    heading_source.close()


class HeadingManager:
    def __init__(self) -> None:
        self.mp_manager = multiprocessing.get_context("spawn").Manager()

        self.heading_source: Optional[HeadingSource] = None
        self.mp_commands: multiprocessing.Queue[Any] = multiprocessing.Queue()
        """
        Status message queue for multiprocessing process
        """
        self.mp_status: multiprocessing.Queue[str] = multiprocessing.Queue()
        """
        Status message queue for multiprocessing process
        """

        self.mp_disconnect = self.mp_manager.Value("i", 0)
        """
        Disconnect signal for multiprocessing process
        """

        self.mp_values: multiprocessing.Queue[tuple[str, Any]] = multiprocessing.Queue()
        """
        CS packet queue for multiprocessing process
        """

        self.heading_source_types: dict[str, Type[HeadingSource]] = {
            "Static": HeadingStatic,
            "Encoder": HeadingEncoder,
            "AHRS Socket": HeadingAHRS,
            "AHRS USB": HeadingAHRSUSB,
            "AHRS FTDI": HeadingAHRSFTDI,
        }

        self.mp_process: Optional[multiprocessing.Process] = None

    def get_heading_source_types(self) -> list[str]:
        return list(self.heading_source_types.keys())

    def start(self) -> None:
        if self.mp_process is not None:
            return
        while not self.mp_commands.empty():
            self.mp_commands.get()
        while not self.mp_status.empty():
            self.mp_status.get()
        while not self.mp_values.empty():
            self.mp_values.get()
        self.mp_disconnect.set(0)
        self.mp_process = multiprocessing.Process(
            target=HeadingWorker,
            args=(
                self.heading_source,
                self.mp_commands,
                self.mp_status,
                self.mp_disconnect,
                self.mp_values,
            ),
        )
        self.mp_process.start()

    def stop(self) -> None:
        self.mp_disconnect.set(1)
        if self.mp_process is not None:
            self.mp_process.join()
            self.mp_process = None

    def update_parameter(self, key: str, value: Any) -> None:
        self.mp_commands.put((key, value))

    def create(self, heading_source: HeadingSource) -> None:
        self.heading_source = heading_source
        if self.mp_process is not None:
            self.mp_commands.put(heading_source)

    def initialize(self) -> None:
        if self.mp_process is not None:
            self.mp_commands.put("initialize")

    def close(self) -> None:
        if self.mp_process is not None:
            self.mp_commands.put("close")
