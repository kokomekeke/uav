from __future__ import annotations

import logging
import threading
import time
from queue import Queue
from typing import Any, Callable, Optional

import sqlalchemy

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
from pysagax.common.loop import Loop
from pysagax.communication.broadcast import RX
from pysagax.communication.pub_sub import SUB
from pysagax.communication.req_rep_tcp import REQ
from pysagax.gnd.database import ComIntDatabase, UAVEntity
from pysagax.message.data_types import DataType
from pysagax.util.get_ip import get_ip


class UAVConnection(threading.Thread):
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
    ) -> None:
        self.daemon = True
        self.running = True
        self.uav_db_id = uav_entity.uav_id
        self.uav_label = uav_entity.uav_label
        self.packet_callback = packet_callback
        self.target_id = 1

        self.uav_address = uav_entity.uav_address
        self.uav_command_port = 5556
        self.own_address = get_ip(self.uav_address)
        self.own_stream_udp_port = 1000
        return super().__init__()

    def send_command(
        self, cmd: proto_cmd.Command, address: str, port: int
    ) -> Optional[proto_cmd.Response]:

        cmd_zmq = REQ(address_server=address, port_server=port)
        cmd_zmq.connect()
        resp = proto_cmd.Response()
        resp_raw = cmd_zmq.send(cmd.SerializeToString(), timeout=2000)
        cmd_zmq.disconnect()
        if resp_raw is None:
            return None
        resp.FromString(resp_raw)
        return resp

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
        self.send_command(cmd_stream_start, self.uav_address, self.uav_command_port)

    def stream_stop(self) -> None:
        cmd_stream_start = proto_cmd.Command()
        cmd_stream_start.instruction = proto_cmd.STREAM_STOP
        cmd_stream_start.target.id = self.target_id
        cmd_stream_start.target.address = self.own_address
        cmd_stream_start.target.port = self.own_stream_udp_port
        self.send_command(cmd_stream_start, self.uav_address, self.uav_command_port)

    def run(self) -> None:
        self.stream_start()
        client = RX(self.own_stream_udp_port)
        all_groups = [group.value for group in DataType]
        client.connect(group=all_groups)
        while self.running:
            data, data_type = client.recv(timeout=1000) or (b"*", "*")
            if data_type in ["*", None]:
                continue
            data_type_object = DataType(data_type)
            stream_packet = DataType.to_message(data_type_object)
            stream_packet.ParseFromString(data)
            if isinstance(stream_packet, proto_data.Measurement):
                self.packet_callback(self.uav_db_id, stream_packet)
        self.stream_stop()


class CommAggregate(Loop):
    """Background process for connecting to the CoreService stream interface and receiving binary data from there"""

    def __init__(
        self,
        db: ComIntDatabase,
        *args,
        **kwargs,
    ) -> None:
        self._db: ComIntDatabase = db
        self._app: Optional[Any] = None
        self._uavs : dict[int, UAVConnection] = {}
        Loop.__init__(self, *args, **kwargs)

    def __call__(
        self,
        *args,
        **kwargs,
    ) -> None:
        self._app = self._db.get_app_instance()
        return super()._call(*args, **kwargs)

    def _recv_thread(self) -> None:
        pass

    def _receive_packet(
        self,
        uav_id: int,
        packet: (
            proto_data.Telemetry
            | proto_data.Measurement
            | proto_data.Event
            | proto_data.OperationalError
        ),
    ) -> None:
        assert self._app
        with self._app.app_context():
            uav_entity: UAVEntity | None = UAVEntity.query.get(uav_id)
            if uav_entity is None:
                self._logger.error(f"UAVEntity {uav_id} not found in DB!")
                return
            # TODO
            uav_entity.last_seen = sqlalchemy.func.now()
            self._db.commit()
        pass

    def _loop(self) -> None:
        assert self._app
        with self._app.app_context():
            all_uavs = (
                UAVEntity.query.order_by(UAVEntity.uav_id.asc())
                .filter_by(active=True)
                .all()
            )
            db_active_uavs = set([uav.uav_id for uav in all_uavs])
            connected_uavs = set(self._uavs.keys())
            to_be_activated = db_active_uavs - connected_uavs
            to_be_deactivated = connected_uavs - db_active_uavs
            for uav_id in to_be_deactivated:
                uav_conn = self._uavs[uav_id]
                self._logger.info(f"Deactivating #{uav_id} {uav_conn.uav_label} ({uav_conn.uav_address})")
                uav_conn.running = False
                uav_conn.join()
                del self._uavs[uav_id]
                self._logger.info(f"Deactivated #{uav_id} {uav_conn.uav_label} ({uav_conn.uav_address})")

            to_be_activated_entities = [uav for uav in all_uavs if uav.uav_id in to_be_activated]

            for uav_entity in to_be_activated_entities:
                self._logger.info(f"Activating #{uav_entity.uav_id} {uav_entity.uav_label} ({uav_entity.uav_address})")
                uav_conn = UAVConnection(uav_entity, self._receive_packet)
                self._uavs[uav_entity.uav_id] = uav_conn
                uav_conn.start()
                self._logger.info(f"Activated #{uav_conn.uav_db_id} {uav_conn.uav_label} ({uav_conn.uav_address})")



        time.sleep(1)
        pass
