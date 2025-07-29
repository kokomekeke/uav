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

from pysagax.util.queue_put import queue_put

import queue
import multiprocessing as mp


# TODO: define control actions here for control message handler thread
# class ControlAction(enum.Enum):
#     SETUP = 1
#     RESET = 2


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class UAVConnection(mp.Process):
    """
    Class that can handle the communication with a single sensor in a process.

    It runs 3 threads:
    - main: handle the incoming data through UDP stream connection
    - command: wait for command messages coming in the queue. Send them and wait for response
    - TODO: control-message: handle instructions coming from UAVConnectionHandler.
        This could do stuff like stream level modification or assemble more complicated command messages if neeeded
    """

    def __init__(
        self,
        uav_entity: UAVEntity,
        streaming_level: proto_cmd.StreamTarget.StreamLevel,
        stream_out_q: queue.Queue,
        command_q: queue.Queue,
        response_q: queue.Queue,
        stop_event: mp.Event,
        level: Any,
    ) -> None:
        super().__init__()
        self._logger = logging.getLogger(f"UAVConnection#{uav_entity.uav_id:02d}")
        self._logger.setLevel(level)
        self.daemon = True
        self.uav_db_id = uav_entity.uav_id
        self.uav_label = uav_entity.uav_label
        self.streaming_level = streaming_level

        self._stream_out_q = stream_out_q
        self._command_q = command_q
        self._response_q = response_q

        self._stop_event = stop_event

        self.control_pipe_parent, self.control_pipe_child = mp.Pipe()

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
        self.last_interacted_ts = time.time()  # TODO: do we even need this ???
        self.reconnect_timeout = 10.0  # seconds

    def send_command(
        self, cmd: proto_cmd.Command, timeout: Optional[int] = 2
    ) -> Optional[proto_cmd.Response]:
        # TODO: always reopen connection?
        # TODO: ideal timeout
        self._logger.trace(f"sending command: {cmd}")
        cmd_zmq = REQ(
            address_server=self.uav_address, port_server=self.uav_command_port
        )
        cmd_zmq.connect()
        resp = proto_cmd.Response()
        resp_raw = cmd_zmq.send(cmd.SerializeToString(), timeout=timeout * 1000)
        cmd_zmq.disconnect()
        if resp_raw is None:
            self._logger.warning(f"No response for command: {cmd}")
            return None
        resp.ParseFromString(resp_raw)
        self._logger.trace(f"received response: {resp}")
        return resp

    def query_sysinfo(self) -> None:

        cmd_sysinfo_query = proto_cmd.Command()
        cmd_sysinfo_query.instruction = proto_cmd.INFO
        resp = self.send_command(cmd_sysinfo_query)
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
        cmd_stream_start.target.level = self.streaming_level
        cmd_stream_start.target.address = self.own_address
        cmd_stream_start.target.port = self.own_stream_udp_port

        # TODO: think about ideal timeout values, move to config
        cmd_stream_start.target.heartbeat_timeout = 1
        cmd_stream_start.target.telemetry_timeout = 1
        resp = self.send_command(cmd_stream_start)
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
        cmd_stream_stop = proto_cmd.Command()
        cmd_stream_stop.instruction = proto_cmd.STREAM_STOP
        cmd_stream_stop.target.id = self.target_id
        cmd_stream_stop.target.address = self.own_address
        cmd_stream_stop.target.port = self.own_stream_udp_port
        resp = self.send_command(cmd_stream_stop)
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

    def _handle_control_messages(self):
        """Thread to handle control messages for setup, reset, etc."""
        while not self._stop_event.is_set():
            time.sleep(1)
        return
        # TODO: is this needed?
        while not self._stop_event.is_set():
            if self.control_pipe_child.poll(timeout=0.1):
                try:
                    msg = self.control_pipe_child.recv()

                    if msg.action == ControlAction.SETUP:
                        pass  # do stuff

                    elif msg.action == ControlAction.RESET:
                        pass  # do stuff

                except Exception as e:
                    print(f"Control message error in sensor {self.sensor_id}: {e}")

    def _handle_commands(self):
        """Thread to handle incoming commands from the command queue"""
        while not self._stop_event.is_set():
            try:
                # TODO: timeout for send_command return and handle no answer
                command = self._command_q.get(timeout=0.2)
                response = self.send_command(command)
                self._response_q.put(response)
            except queue.Empty:
                continue
            except Exception as e:
                self._logger.exception(f"Error in command handler: {e}")
                time.sleep(0.2)

    def run(self) -> None:
        # SETUP
        mp.current_process().name = f"UAVConnection#{self.uav_db_id:02d}"
        self.query_sysinfo()
        self.stream_start()
        client = self._create_stream_client()

        # Start control message handler thread
        control_thread = threading.Thread(target=self._handle_control_messages)
        control_thread.daemon = True
        control_thread.start()

        # Start command handler thread
        cmd_thread = threading.Thread(target=self._handle_commands)
        cmd_thread.daemon = True
        cmd_thread.start()

        # ACT
        self._run_upd_stream(client)

        # TEARDOWN
        self.stream_stop()
        control_thread.join()
        self._logger.debug("Control thread joined")
        cmd_thread.join()
        self._logger.debug("Command thread joined")

        # TODO: free up TCP and UDP ports

    def _create_stream_client(self):
        client = RX(self.own_stream_udp_port)
        all_groups = [group.value for group in DataType]
        client.connect(group=all_groups)
        self._logger.info(
            f"UDP port {self.own_stream_udp_port} is open for {self.uav_label} ({self.uav_address}) "
        )

        return client

    def _run_upd_stream(self, client):
        """Receives and handles data coming through the UDP stream channel"""
        while not self._stop_event.is_set():
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
            queue_put(
                self._stream_out_q,
                (self.uav_db_id, stream_packet),
                timeout=0.1,
            )
            # self._stream_out_q.put((self.uav_db_id, stream_packet)) # TODO use queue_put?
            self.last_interacted_ts = time.time()
