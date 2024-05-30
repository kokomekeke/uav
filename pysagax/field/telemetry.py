from __future__ import annotations
from multiprocessing.managers import DictProxy
from queue import Queue
import queue
import shlex
import time
import shutil
import pickle
import socket
import logging

from typing import Any, Generator, Iterable, Optional

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
        self._latest_cs_telemetry_packet = proto_data.Telemetry()
        self._latest_cs_telemetry_received_time = time.time()
        self._cs_telemetry_queue: Optional[Queue] = None
        self._heading_status_queue: Optional[Queue] = None
        self._latest_packets_proxy: Optional[DictProxy] = None
        self._latest_se_proxy: Optional[DictProxy] = None
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
        cs_telemetry_queue: Queue[proto_data.Telemetry],
        heading_status_queue: Queue[Any],
        latest_packets_proxy: Optional[DictProxy] = None,
        latest_se_proxy: Optional[DictProxy] = None,
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_out = comm_queue_out
        self._cs_telemetry_queue = cs_telemetry_queue
        self._heading_status_queue = heading_status_queue
        self._latest_packets_proxy = latest_packets_proxy
        self._latest_se_proxy = latest_se_proxy
        return super()._call(*args, **kwargs)

    def _get_from_cs(self) -> None:

        assert self._cs_telemetry_queue is not None
        latest_cs_telemetry_packet = self._latest_cs_telemetry_packet
        while not self._cs_telemetry_queue.empty():
            latest_cs_telemetry_packet = self._cs_telemetry_queue.get()
            self._latest_cs_telemetry_received_time = time.time()
        assert isinstance(latest_cs_telemetry_packet, proto_data.Telemetry)
        if self._latest_cs_telemetry_received_time < time.time() - 5.0:
            # cs telemetry expected at least every 5 secs
            self._latest_cs_telemetry_packet = proto_data.Telemetry()
        else:
            self._latest_cs_telemetry_packet = latest_cs_telemetry_packet
        self._telemetry_packet.source.CopyFrom(self._latest_cs_telemetry_packet.source)
        self._telemetry_packet.recording.CopyFrom(
            self._latest_cs_telemetry_packet.recording
        )

    def _construct_sysinfo_packet(self) -> None:
        assert self._comm_queue_out is not None
        self._sysinfo_packet.Clear()
        total, used, free = shutil.disk_usage(self._data_partition_path)
        self._sysinfo_packet.hardware.hostname = self._hostname
        self._sysinfo_packet.hardware.disk = total // (2**20)  # MiB
        self._sysinfo_packet.software.pysagax_version = pysagax.__version__  # type: ignore
        self._sysinfo_packet.heading.MergeFrom(self._heading_status_packet)
        # TODO CoreService version
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
                    self._protobuf_to_log(
                        self._heading_status_packet,
                        "Heading updated: {}",
                        level=logging.DEBUG,
                    )
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
        self._telemetry_packet.scanengine_state = (
            self._latest_se_proxy["state"]
            if self._latest_se_proxy is not None and "state" in self._latest_se_proxy
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
