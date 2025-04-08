from __future__ import annotations
import logging
import math
import queue
from queue import Queue
import time

import sqlalchemy
from typing import Any, Callable, Optional
from pysagax.gnd.database import ComIntDatabase, ComIntDetectionEntity, UAVEntity
from pysagax.util.queue_put import queue_put

from pysagax.util.run_once import run_once

from pysagax.gnd.uav_report import UAVReport

import pysagax.message.data_pb2 as proto_data

from pysagax.common.loop import Loop

from pysagax.gnd.database import ComIntDatabase, ComIntDetectionEntity, UAVEntity


class MeasurementProcessor(Loop):
    """Processes packets received from UAVs through the UDP stream connection"""

    def __init__(
        self,
        db: ComIntDatabase,
        db_commit_frequency: float,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self._db: ComIntDatabase = db
        self._app: Optional[Any] = None

        self._in_queue: Optional[Queue] = None
        self._to_monitoring_queue: Optional[Queue] = None
        self._last_commit = time.time()
        self._measurements_to_add = []
        self._uavs_to_update = {}
        self.db_commit_frequency = db_commit_frequency


    def __call__(
        self,
        in_queue: Queue, 
        to_monitoring_queue: Queue,
        *args,
        **kwargs,
    ) -> None:
        self._in_queue = in_queue
        self._to_monitoring_queue = to_monitoring_queue
        self._app = self._db.get_app_instance()
        return super()._call(*args, **kwargs)


    def _receive_telemetry(
        self, uav_entity: UAVEntity, packet: proto_data.Telemetry
    ) -> None:
        """TODO Hanlde telemetry packets"""
        self._logger.debug(
            f"Got a Telemetry from {uav_entity.uav_label}! Hostname is {packet.hardware.hostname}"
        )
        report = UAVReport(
            uav_entity.uav_id, uav_entity.uav_label, uav_entity.uav_address
        )
        # report.update_from_sysinfo(sysinfo)
        report.update_from_telemetry(packet)
        queue_put(self._to_monitoring_queue, report, 1, self._logger, "Telemetry to monitoring")
        return

        # TODO: plan how this health report will work and do it

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
        self._logger.trace(
            f"Got a Measurement from {uav_entity.uav_label}! Detection count is {len(packet.detection)}"
        )
        self._logger.trace(f"Measurement packet delay: {time.time()-packet.time.seconds-packet.time.nanos/1e9}")
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
            self._measurements_to_add.append(new_meas_entity)
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
        return uav_entity
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
            match type(packet):
                case proto_data.Telemetry: self._receive_telemetry(uav_entity, packet)
                case proto_data.Measurement: uav_entity = self._receive_measurement(uav_entity, packet)
                case proto_data.Event: self._receive_event(uav_entity, packet)
                case proto_data.OperationalError: self._receive_operror(uav_entity, packet)
                case _: self._logger.critical(f"Unknown packet type ({type(packet)})") 
            uav_entity.last_seen = sqlalchemy.func.now()

            self._uavs_to_update[uav_entity.uav_id] = uav_entity

    @run_once(timeout=1)
    def _log_queue_filled(self, size):
        self._logger.warning(f"input queue has {size} elements waiting to be processed")
        # If you see this warning a lot, consider increasing db_commit_frequency


    def _loop(self) -> None:
        try:
            # Get  from the queue with a timeout
            id, packet = self._in_queue.get(timeout=1.0)
            self._receive_packet(id, packet)
            in_q_size = self._in_queue.qsize()
            if  in_q_size > 10:
                self._log_queue_filled(in_q_size)
            if time.time() - self._last_commit > self.db_commit_frequency:
                # only commit the DB changes after db_commit_frequency seconds have elapsed
                # TODO: we should use a DB technology where transactions are cheap
                #       we might want to remove this and commit every update instantly 
                #       when we have the new db
                with self._app.app_context():
                    self._logger.trace(f"Adding {len(self._measurements_to_add)} detections to DB")
                    self._logger.trace(f"Updating {len(self._uavs_to_update)} uavs in DB")
                    for meas_entity in self._measurements_to_add:
                        self._db.add(meas_entity)
                    self._measurements_to_add = []

                    for uav_id, uav_entity in self._uavs_to_update.items():
                        # we only want to owerwrite the fields updated in this module
                        # # TODO: improve ?
                        old_uav_entity: UAVEntity | None = UAVEntity.query.get(uav_id)
                        old_uav_entity.last_seen = uav_entity.last_seen
                        old_uav_entity.last_pos_lat = uav_entity.last_pos_lat
                        old_uav_entity.last_pos_lon = uav_entity.last_pos_lon
                        old_uav_entity.last_pos_altitude = uav_entity.last_pos_altitude
                        old_uav_entity.last_pos_q0 = uav_entity.last_pos_q0
                        old_uav_entity.last_pos_q1 = uav_entity.last_pos_q1
                        old_uav_entity.last_pos_q2 = uav_entity.last_pos_q2
                        old_uav_entity.last_pos_q3 = uav_entity.last_pos_q3
                        old_uav_entity.last_seen = uav_entity.last_seen

                    self._db.commit()
                    self._last_commit = time.time()
        except queue.Empty:
            return  # No packets to process
        except Exception as e:
            self._logger.exception(f"Error in MeasurementProcessor: {e}")
            time.sleep(0.1)