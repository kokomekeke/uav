from __future__ import annotations

import logging
import math
import time
import queue
from typing import Any, Callable, Optional

import multiprocessing as mp

from pysagax.common.loop import Loop
from pysagax.gnd.database import ComIntDatabase, ComIntDetectionEntity, UAVEntity
from pysagax.util.queue_put import queue_put
from pysagax.gnd.sensorconnection import UAVConnection
import pysagax.message.command_pb2 as proto_cmd


class UAVConnectionHandler:
    """
    Provides a clean interface for the UAVConnections
    running in separate processes.

    Handles all the hassles of multiprocessing, so it's easy
    to interact with UAVConnections as if they were only separate threads
    """

    def __init__(
        self,
        uav_entity: UAVEntity,
        to_measurement_processor_q: queue.Queue,
        level: Any,
    ):
        self._logger = logging.getLogger(
            f"UAVConnectionHandler#{uav_entity.uav_id:02d}"
        )
        self._logger.setLevel(level)

        # TODO: Do I need to access the Commander's multiprocessing manager here?
        # TODO: queue sizes=??
        self._command_q = mp.Queue()
        self._response_q = mp.Queue()
        self._stop_event = mp.Event()
        self._uav = UAVConnection(
            uav_entity=uav_entity,
            stream_out_q=to_measurement_processor_q,
            command_q=self._command_q,
            response_q=self._response_q,
            stop_event=self._stop_event,
            level=level,
        )

        self.id, self.label, self.address = (
            uav_entity.uav_id,
            uav_entity.uav_label,
            uav_entity.uav_address,
        )

        # More complicated instructions that'd require function calls are triggered through the control pipe
        # TODO: did we end up using it?
        self._control_pipe = self._uav.control_pipe_parent

    def start(self):
        """start the UAVConnection process"""
        self._uav.start()

    def stop(self):
        """Stop the UAVConnection process"""
        self._logger.debug("Stopping UAV connection")
        self._stop_event.set()

    def join(self):
        self._logger.trace("Waiting for UAV connection to join...")
        self._uav.join()
        self._logger.trace("UAV connection joined!")

    def send_command(
        self, cmd: proto_cmd.Command, timeout: Optional[int] = 1
    ) -> Optional[proto_cmd.Response]:
        self._command_q.put(cmd)
        try:
            rsp = self._response_q.get(timeout=timeout)
        except queue.Empty:
            self._logger.warning(
                f"UAVConnection didn't answer within {timeout} seconds the following command: {cmd}"
            )
            return None
        return rsp

    # def query_sysinfo(self) -> None:
    #     pass

    # def stream_start(self) -> None:
    #     pass

    # def stream_stop(self) -> None:
    #     pass


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
        self._uavs: dict[int, UAVConnectionHandler] = {}  # uav_id -> UAV handler dict
        self._commands_from_api: Optional[queue.Queue] = None
        self._responses_to_api: Optional[queue.Queue] = None
        self._uavs_to_measurement_processor: Optional[queue.Queue] = None

        super().__init__(*args, **kwargs)

    def __call__(
        self,
        commands_from_api: queue.Queue[Any],
        responses_to_api: queue.Queue[Any],
        uavs_to_measurement_processor: queue.Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._app = self._db.get_app_instance()
        self._commands_from_api = commands_from_api
        self._responses_to_api = responses_to_api
        self._uavs_to_measurement_processor = uavs_to_measurement_processor
        return super()._call(*args, **kwargs)

    def _refresh_active_sensor_list(self):
        """Decides which sensors need to get activated or deactivated"""
        assert self._app
        with self._app.app_context():
            db_active_uavs = (
                UAVEntity.query.order_by(UAVEntity.uav_id.asc())
                .filter_by(active=True)
                .all()
            )
            should_be_active_uav_ids = set([uav.uav_id for uav in db_active_uavs])
            connected_uav_ids = set(self._uavs.keys())
            to_be_activated_ids = should_be_active_uav_ids - connected_uav_ids
            to_be_deactivated_ids = connected_uav_ids - should_be_active_uav_ids

            self._deactivate_uavs(to_be_deactivated_ids)

            self._activate_uavs(db_active_uavs, to_be_activated_ids)

    def _activate_uavs(self, db_active_uavs: list[UAVEntity], to_be_activated: set):
        """ "Activate UAVs given their ids"""
        # Get the DB rows from the ids
        to_be_activated_entities = [
            uav for uav in db_active_uavs if uav.uav_id in to_be_activated
        ]

        for uav_entity in to_be_activated_entities:
            self._logger.info(
                f"Activating #{uav_entity.uav_id} {uav_entity.uav_label} ({uav_entity.uav_address})"
            )
            uav_conn = UAVConnectionHandler(
                uav_entity, self._uavs_to_measurement_processor, self._logger.level
            )
            self._uavs[uav_entity.uav_id] = uav_conn
            uav_conn.start()
            self._logger.info(
                f"Activated #{uav_conn.id} {uav_conn.label} ({uav_conn.address})"
            )

    def _deactivate_uavs(self, to_be_deactivated):
        """Deactivate UAVs given by their ids in a set"""
        for uav_id in to_be_deactivated:
            uav_conn = self._uavs[uav_id]
            self._logger.info(
                f"Deactivating #{uav_id} {uav_conn.label} ({uav_conn.address})"
            )
            uav_conn.stop()
            uav_conn.join()
            del self._uavs[uav_id]
            self._logger.info(
                f"Deactivated #{uav_id} {uav_conn.label} ({uav_conn.address})"
            )

    def _loop(self) -> None:
        self._refresh_active_sensor_list()
        time.sleep(1)
