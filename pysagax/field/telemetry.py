from __future__ import annotations
from multiprocessing.managers import DictProxy
from queue import Queue
import queue
import shlex
import time
import shutil
import pickle
import socket

from typing import Any, Generator, Iterable, Optional

from google.protobuf.json_format import MessageToJson
import pysagax

import pysagax.message.data_pb2 as proto_data
import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.heading_pb2 as proto_heading

from pysagax.common.loop import Loop


class Telemetry(Loop):
    """Background process for collecting telemetry data and creating Telemetry messages"""

    def __init__(
        self, data_partition_path: str = "/", interval: float = 0.25, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._comm_queue_out: Optional[Queue] = None
        self._cs_commands_queue: Optional[Queue] = None
        self._cs_responses_queue: Optional[Queue] = None
        self._heading_status_queue: Optional[Queue] = None
        self._latest_packets_proxy: Optional[DictProxy] = None
        self._telemetry_packet = proto_data.Telemetry()
        self._sysinfo_packet = proto_cmd.SystemInfo()
        self._heading_status_packet = proto_heading.HeadingStatus()
        self._data_partition_path = data_partition_path
        self._interval = interval
        self._hostname = socket.gethostname()
        self._latest_heading_status_time = 0.0

    def __call__(
        self,
        comm_queue_out: Queue[Any],
        cs_commands_queue: Queue[Any],
        cs_responses_queue: Queue[Any],
        heading_status_queue: Queue[Any],
        latest_packets_proxy: Optional[DictProxy] = None,
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_out = comm_queue_out
        self._cs_commands_queue = cs_commands_queue
        self._cs_responses_queue = cs_responses_queue
        self._heading_status_queue = heading_status_queue
        self._latest_packets_proxy = latest_packets_proxy
        return super()._call(*args, **kwargs)

    def _cs_execute(
        self, commands: Iterable[str], timeout: Optional[float] = 1
    ) -> Generator[tuple[str, list[str]], None, None]:
        """Send a list of commands to CoreService, return the result."""
        assert self._cs_commands_queue is not None
        assert self._cs_responses_queue is not None
        while not self._cs_responses_queue.empty():
            self._cs_responses_queue.get()
        for command in commands:
            if command[-1:] != ";":
                command += ";"
            self._cs_commands_queue.put(command)
        last_command = ""
        try:
            for command in commands:
                last_command = command
                command_recv = ""
                response: Optional[str] = None
                while command_recv.strip("\r\n\t ;") != command.strip("\r\n\t ;"):
                    command_recv, response = self._cs_responses_queue.get(
                        timeout=timeout
                    )
                if response is None:
                    self._logger.warning(f"CS empty response to {last_command}")
                    return None
                response = response.strip("\r\n\t ;")
                response_parts = shlex.split(response)
                error_code = int(response_parts[0])
                if error_code > 0:
                    self._logger.warning(f"Error {response} for cmd {command}")
                yield command, response_parts
        except queue.Empty:
            self._logger.error(f"CS not responding to {last_command}")
            while not self._cs_commands_queue.empty():
                self._cs_commands_queue.get()

    def _get_from_cs(self) -> None:
        for command, response in self._cs_execute(
            [
                "SOURCE:Status?",
                "RECORDING:Status?",
                "SOURCE:Length?",
                "SOURCE:Position?",
            ]
        ):
            self._logger.debug(f" * {command} * {str(response)} *")
            match command:
                case "SOURCE:Status?":
                    if len(response) < 3:
                        self._logger.warning(
                            f"Invalid CS response for Status?: {str(response)}"
                        )
                        return
                    ready = bool(int(response[1]))
                    started = bool(int(response[2]))
                    self._telemetry_packet.source.status = (
                        proto_data.Telemetry.Source.DISABLED
                        if not ready
                        else (
                            proto_data.Telemetry.Source.RUNNING
                            if started
                            else proto_data.Telemetry.Source.ENABLED
                        )
                    )
                case "RECORDING:Status?":
                    if len(response) < 3:
                        self._logger.warning(
                            f"Invalid CS response for Recording?: {str(response)}"
                        )
                        return
                    enabled = bool(int(response[1]))
                    running = bool(int(response[2]))
                    self._telemetry_packet.recording.status = (
                        proto_data.Telemetry.Recording.DISABLED
                        if not enabled
                        else (
                            proto_data.Telemetry.Recording.RUNNING
                            if running
                            else proto_data.Telemetry.Recording.ENABLED
                        )
                    )
                case "SOURCE:Length?":
                    if response[0] == "0":
                        self._telemetry_packet.source.length = int(response[1])

                case "SOURCE:Position?":
                    if response[0] == "0":
                        self._telemetry_packet.source.position = int(response[1])

            pass

    def _construct_sysinfo_packet(self) -> None:
        assert self._comm_queue_out is not None
        self._sysinfo_packet.Clear()
        total, used, free = shutil.disk_usage(self._data_partition_path)
        self._sysinfo_packet.hardware.hostname = self._hostname
        self._sysinfo_packet.hardware.disk = total // (2**20)  # MiB
        self._sysinfo_packet.software.pysagax_version = pysagax.__version__  # type: ignore
        self._sysinfo_packet.heading.MergeFrom(self._heading_status_packet)
        try:
            _, resp = next(self._cs_execute(["CORE:Version?"]))
            if resp[0] == "0":
                self._sysinfo_packet.software.cs_version = (
                    f"{resp[1]}.{resp[2]}.{resp[3]}"  # major.minor.patch
                )
                if resp[4]:
                    self._sysinfo_packet.software.cs_version += (
                        f"-{resp[4]}"  # -prerelease
                    )
                if resp[5]:
                    self._sysinfo_packet.software.cs_version += f"+{resp[5]}"  # +build
                if resp[6]:
                    self._sysinfo_packet.software.cs_version += (
                        f" ({resp[6]})"  # (vcs tag)
                    )
        except StopIteration:  # CS not responding
            self._sysinfo_packet.software.cs_version = "N/A"
        self._logger.debug("SystemInfo packet ready")
        if self._latest_packets_proxy is not None:
            self._latest_packets_proxy["SystemInfo"] = pickle.dumps(
                self._sysinfo_packet
            )
        self._comm_queue_out.put(self._sysinfo_packet)

    def _measure_hardware_stats(self) -> None:

        total, used, free = shutil.disk_usage(self._data_partition_path)

        # print("Total: %d GiB" % (total // (2**30)))
        # print("Used: %d GiB" % (used // (2**30)))
        # print("Free: %d GiB" % (free // (2**30)))
        self._telemetry_packet.hardware.disk_usage = used // (2**20)  # MiB

    def _get_heading_module_info(self) -> None:
        assert self._heading_status_queue is not None
        while True:
            try:
                status_packet = self._heading_status_queue.get_nowait()
                if isinstance(status_packet, proto_heading.HeadingStatus):
                    self._heading_status_packet = status_packet
                    self._latest_heading_status_time = time.time()
                    logged_message = (
                        MessageToJson(self._heading_status_packet, indent=0)
                        .replace("\n", "")
                        .replace("\r", "")
                    )
                    self._logger.info(f"Heading updated: {logged_message}")
                    if self._latest_packets_proxy is not None:
                        self._latest_packets_proxy["HeadingStatus"] = pickle.dumps(
                            self._heading_status_packet
                        )

                    self._construct_sysinfo_packet()
                else:
                    break
            except queue.Empty:
                break

    def _push_finished_packet(self) -> None:
        assert self._comm_queue_out is not None
        self._telemetry_packet.heading.status = (
            "Running"
            if time.time() < self._latest_heading_status_time + 6
            else "Unknown"
        )
        self._telemetry_packet.hardware.hostname = self._hostname
        self._telemetry_packet.time.GetCurrentTime()
        self._logger.debug(
            f"Telemetry packet ready {self._telemetry_packet.time.ToJsonString()}"
        )
        if self._latest_packets_proxy is not None:
            self._latest_packets_proxy["Telemetry"] = pickle.dumps(
                self._telemetry_packet
            )

        self._comm_queue_out.put(self._telemetry_packet)
        self._telemetry_packet = proto_data.Telemetry()

    def _pre_loop(self) -> None:
        self._construct_sysinfo_packet()

    def _loop(self) -> None:
        assert self._comm_queue_out is not None

        # try:
        #     cs_stream_packet = self._cs_queue_in.get(block=False)
        #     if isinstance(cs_stream_packet, CoreServiceDebugPacket):
        #         if cs_stream_packet.title == "t":  # timestamp is the last packet

        #             self._push_finished_packet()
        # except queue.Empty:
        #     pass
        self._get_heading_module_info()
        self._measure_hardware_stats()
        self._get_from_cs()
        if self._sysinfo_packet.software.cs_version == "N/A":
            self._construct_sysinfo_packet()
        self._push_finished_packet()
        time.sleep(self._interval)
        # Send response to Communicator
