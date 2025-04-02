from __future__ import annotations

import logging
import socket
import threading
import time
from contextlib import closing
from typing import Any, Callable, Optional

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
from pysagax.communication.broadcast import RX
from pysagax.communication.req_rep_tcp import REQ
from pysagax.gnd.database import ComIntDatabase, ComIntDetectionEntity, UAVEntity
from pysagax.message.data_types import DataType
from pysagax.util.get_ip import get_ip





def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class SensorConnection(threading.Thread):
    def __init__(
        self,
        uav_entity: UAVEntity,
        packet_callback: Callable[
            [
                int,
                proto_data.Telemetry
                | proto_data.Measurement
                | proto_data.Event
                | proto_data.OperationalError,
            ],
            None,
        ],
        level: Any,
    ) -> None:
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.setLevel(level)
        self.daemon = True
        self.running = True
        self.uav_db_id = uav_entity.uav_id
        self.uav_label = uav_entity.uav_label
        self.packet_callback = packet_callback
        self.target_id = 1

        # check if address also contains port
        if len(uav_entity.uav_address.split(":")) == 2:
            self.uav_address, self.uav_command_port = uav_entity.uav_address.split(":")
        else:
            self.uav_address = uav_entity.uav_address
            self.uav_command_port = 5556
        self.own_address = get_ip(self.uav_address)
        self.own_stream_udp_port = find_free_port()
        self.sysinfo = proto_cmd.SystemInfo()
        self.last_interacted_ts = time.time()
        self.reconnect_timeout = 10.0  # seconds

    def send_command(
        self, cmd: proto_cmd.Command, address: str, port: int
        ) -> Optional[proto_cmd.Response]:
        self._logger.critical("COMMAND SEN")
        cmd_zmq = REQ(address_server=address, port_server=port)
        cmd_zmq.connect()
        resp = proto_cmd.Response()
        resp_raw = cmd_zmq.send(cmd.SerializeToString(), timeout=2000)
        cmd_zmq.disconnect()
        if resp_raw is None:
            return None
        resp.ParseFromString(resp_raw)
        return resp

    def query_sysinfo(self) -> None:

        cmd_sysinfo_query = proto_cmd.Command()
        cmd_sysinfo_query.instruction = proto_cmd.INFO
        resp = self.send_command(
            cmd_sysinfo_query, self.uav_address, self.uav_command_port
        )
        if resp:
            if resp.HasField("error"):
                self._logger.error(
                    f"SystemInfo query error {resp.error} on {self.uav_address}:{self.uav_command_port}"
                )
            else:
                if resp.HasField("info"):

                    self._logger.info(
                        f"System Info successful on {self.uav_address}:{self.uav_command_port}: "
                        f"PySAGAX {resp.info.software.pysagax_version}, CS {resp.info.software.cs_version}, "
                        f"Heading {resp.info.heading.selected_source_type}"
                    )
                    self.sysinfo.CopyFrom(resp.info)
                else:
                    self._logger.error(
                        f"SystemInfo query unknown on {self.uav_address}:{self.uav_command_port}"
                    )
        else:
            self._logger.error(
                f"SystemInfo timed out on {self.uav_address}:{self.uav_command_port}"
            )

    def stream_start(self) -> None:
        cmd_stream_start = proto_cmd.Command()
        cmd_stream_start.instruction = proto_cmd.STREAM_START
        # TODO: customazible stream levels
        cmd_stream_start.target.id = self.target_id
        cmd_stream_start.target.level = proto_cmd.StreamTarget.StreamLevel.SPECTRUM
        cmd_stream_start.target.address = self.own_address
        cmd_stream_start.target.port = self.own_stream_udp_port

        # TODO: think about ideal timeout values, move to config
        cmd_stream_start.target.heartbeat_timeout = 1
        cmd_stream_start.target.telemetry_timeout = 1
        resp = self.send_command(
            cmd_stream_start, self.uav_address, self.uav_command_port
        )
        if resp:
            if resp.HasField("error"):
                self._logger.error(
                    f"Stream start error {resp.error} on {self.uav_address}:{self.uav_command_port}"
                )
            else:
                self._logger.info(
                    f"Stream start successful on {self.uav_address}:{self.uav_command_port}"
                )
        else:
            self._logger.error(
                f"Stream start timed out on {self.uav_address}:{self.uav_command_port}"
            )

    def stream_stop(self) -> None:
        cmd_stream_start = proto_cmd.Command()
        cmd_stream_start.instruction = proto_cmd.STREAM_STOP
        cmd_stream_start.target.id = self.target_id
        cmd_stream_start.target.address = self.own_address
        cmd_stream_start.target.port = self.own_stream_udp_port
        resp = self.send_command(
            cmd_stream_start, self.uav_address, self.uav_command_port
        )
        if resp:
            if resp.HasField("error"):
                self._logger.error(
                    f"Stream stop error {resp.error} on {self.uav_address}:{self.uav_command_port}"
                )
            else:
                self._logger.info(
                    f"Stream stop successful on {self.uav_address}:{self.uav_command_port}"
                )
        else:
            self._logger.error(
                f"Stream stop timed out on {self.uav_address}:{self.uav_command_port}"
            )

    def run(self) -> None:
        self.query_sysinfo()
        self.stream_start()
        client = RX(self.own_stream_udp_port)
        all_groups = [group.value for group in DataType]
        client.connect(group=all_groups)
        self._logger.info(
            f"UDP port {self.own_stream_udp_port} is open for {self.uav_label} ({self.uav_address}) "
        )
        while self.running:
            data, data_type = client.recv(timeout=1000) or (b"*", "*")
            if data_type in ["*", None]:
                if self.last_interacted_ts + self.reconnect_timeout < time.time():
                    self.query_sysinfo()
                    self.stream_start()
                    self.last_interacted_ts = time.time()
                continue
            data_type_object = DataType(data_type)
            stream_packet = DataType.to_message(data_type_object)
            stream_packet.ParseFromString(data)
            self.packet_callback(self.uav_db_id, stream_packet)
            self.last_interacted_ts = time.time()
        self.stream_stop()
