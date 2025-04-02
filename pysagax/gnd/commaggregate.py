from __future__ import annotations

import logging
import math
import time
from queue import Queue
from typing import Any, Callable, Optional

import sqlalchemy
from pysagax.gnd.uav_report import UAVReport

import pysagax.message.data_pb2 as proto_data
from pysagax.common.loop import Loop
from pysagax.gnd.database import ComIntDatabase, ComIntDetectionEntity, UAVEntity
from pysagax.util.queue_put import queue_put
from pysagax.gnd.sensorconnection import SensorConnection


class CommAggregate(Loop):
    """Background process for managing the connections and communications to the UAVs"""

    def __init__(
        self,
        db: ComIntDatabase,
        *args,
        **kwargs,
    ) -> None:
        self._db: ComIntDatabase = db
        self._app: Optional[Any] = None
        self._uavs: dict[int, SensorConnection] = {}
        self._telemetry_to_monitoring: Optional[Queue] = None
        # Loop.__init__(self, *args, **kwargs)
        super().__init__(*args, **kwargs)

    def __call__(
        self,
        telemetry_to_monitoring: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._app = self._db.get_app_instance()
        self._telemetry_to_monitoring = telemetry_to_monitoring
        return super()._call(*args, **kwargs)

    def _recv_thread(self) -> None:
        pass

    def _receive_telemetry(
        self, uav_entity: UAVEntity, packet: proto_data.Telemetry
    ) -> None:
        self._logger.debug(
            f"Got a Telemetry from {uav_entity.uav_label}! Hostname is {packet.hardware.hostname}"
        )
        telem = packet
        sysinfo = self._uavs[uav_entity.uav_id].sysinfo
        uav_entity.health_report = (
            f"{telem.hardware.hostname}\n{telem.time.ToDatetime()} UTC\n"
            f"PySAGAX {sysinfo.software.pysagax_version}, CS {sysinfo.software.cs_version}\n"
            f"Disk usage: {'{:,}'.format(telem.hardware.disk_usage).replace(',', ' ')} MB / "
            f"{'{:,}'.format(sysinfo.hardware.disk).replace(',', ' ')} MB\n"
            f"Source module {proto_data.Telemetry.Source.Status.Name(telem.source.status)} "
            f"{'{:,}'.format(telem.source.position).replace(',', ' ')} / "
            f"{'{:,}'.format(telem.source.length).replace(',', ' ')} \n"
            f"Recording module {proto_data.Telemetry.Recording.Status.Name(telem.recording.status)} "
            f"{'{:,}'.format(telem.recording.length).replace(',', ' ')}\n"
            f"Heading module {telem.heading.status} [{telem.heading.selected_source_type}]\n"
            f"ScanEngine {telem.scanengine_state}"
        )
        report = UAVReport(
            uav_entity.uav_id, uav_entity.uav_label, uav_entity.uav_address
        )
        report.update_from_sysinfo(sysinfo)
        report.update_from_telemetry(telem)
        assert self._telemetry_to_monitoring is not None
        queue_put(self._telemetry_to_monitoring, report, 1, self._logger, "Telemetry to monitoring")

    def _receive_measurement(
        self, uav_entity: UAVEntity, packet: proto_data.Measurement
    ) -> None:
        self._logger.debug(
            f"Got a Measurement from {uav_entity.uav_label}! Detection count is {len(packet.detection)}"
        )
        for det in packet.detection:
            new_meas_entity = ComIntDetectionEntity()
            new_meas_entity.uav_id = uav_entity.uav_id
            new_meas_entity.frequency = int(det.frequency)
            new_meas_entity.bandwidth = int(det.bandwidth)
            new_meas_entity.snr = det.snr
            new_meas_entity.lob_azim_deg = det.mean_azimuth / math.pi * 180.0
            new_meas_entity.lob_elev_deg = det.mean_elevation / math.pi * 180.0
            new_meas_entity.precision = 1 - (det.deviation / (math.pi * 2))
            new_meas_entity.signal_strength = det.strength
            new_meas_entity.timestamp = packet.time.ToDatetime()
            new_meas_entity.roi_identifier = det.roi_id
            new_meas_entity.uav_pos_lat = packet.heading_data.gps_lat
            new_meas_entity.uav_pos_lon = packet.heading_data.gps_lon
            new_meas_entity.uav_pos_altitude = packet.heading_data.altitude
            if len(packet.heading_data.quaternion) == 4:
                new_meas_entity.uav_pos_q0 = packet.heading_data.quaternion[0]
                new_meas_entity.uav_pos_q1 = packet.heading_data.quaternion[1]
                new_meas_entity.uav_pos_q2 = packet.heading_data.quaternion[2]
                new_meas_entity.uav_pos_q3 = packet.heading_data.quaternion[3]
            self._db.add(new_meas_entity)
        uav_entity.last_pos_lat = packet.heading_data.gps_lat
        uav_entity.last_pos_lon = packet.heading_data.gps_lon
        uav_entity.last_pos_altitude = packet.heading_data.altitude
        if len(packet.heading_data.quaternion) == 4:
            uav_entity.last_pos_q0 = packet.heading_data.quaternion[0]
            uav_entity.last_pos_q1 = packet.heading_data.quaternion[1]
            uav_entity.last_pos_q2 = packet.heading_data.quaternion[2]
            uav_entity.last_pos_q3 = packet.heading_data.quaternion[3]
        else:
            self._logger.warning(
                f"Received quaternion length is {len(packet.heading_data.quaternion)}"
            )
        self._db.commit()

    def _receive_event(self, uav_entity: UAVEntity, packet: proto_data.Event) -> None:
        self._logger.info(
            f"Got a Event from {uav_entity.uav_label}! Event id is {packet.event_id}"
        )

    def _receive_operror(
        self, uav_entity: UAVEntity, packet: proto_data.OperationalError
    ) -> None:
        self._logger.error(
            f"Got an OperationalError from {uav_entity.uav_label}! Error description: {packet.description}"
        )

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
            {
                proto_data.Telemetry: self._receive_telemetry,
                proto_data.Measurement: self._receive_measurement,
                proto_data.Event: self._receive_event,
                proto_data.OperationalError: self._receive_operror,
            }[type(packet)](uav_entity, packet)
            uav_entity.last_seen = sqlalchemy.func.now()
            self._db.commit()
        self._logger.debug("Received packet processed!")

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
                self._logger.info(
                    f"Deactivating #{uav_id} {uav_conn.uav_label} ({uav_conn.uav_address})"
                )
                uav_conn.running = False
                uav_conn.join()
                del self._uavs[uav_id]
                self._logger.info(
                    f"Deactivated #{uav_id} {uav_conn.uav_label} ({uav_conn.uav_address})"
                )

            to_be_activated_entities = [
                uav for uav in all_uavs if uav.uav_id in to_be_activated
            ]

            for uav_entity in to_be_activated_entities:
                self._logger.info(
                    f"Activating #{uav_entity.uav_id} {uav_entity.uav_label} ({uav_entity.uav_address})"
                )
                uav_conn = SensorConnection(
                    uav_entity, self._receive_packet, level=self._logger.level
                )
                self._uavs[uav_entity.uav_id] = uav_conn
                uav_conn.start()
                self._logger.info(
                    f"Activated #{uav_conn.uav_db_id} {uav_conn.uav_label} ({uav_conn.uav_address})"
                )

        time.sleep(1)
