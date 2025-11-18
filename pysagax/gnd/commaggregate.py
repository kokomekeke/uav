from __future__ import annotations

import logging
import math
import time
import queue
from typing import Any, Callable, Optional
import threading

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
        to_stream_q: queue.Queue,
        level: Any,
        streaming_level: proto_cmd.StreamTarget.StreamLevel = proto_cmd.StreamTarget.StreamLevel.DETECTION,
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
            streaming_level=streaming_level,
            to_measurement_processor_q=to_measurement_processor_q,
            to_stream_q=to_stream_q,
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
        self._command_q.put(cmd, timeout=timeout)
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

    # TODO: def change_stream_level(self, asdf): pass


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
        self._incoming_command_q: Optional[queue.Queue] = None
        self._outgoing_responses_q: Optional[queue.Queue] = None
        self._uavs_to_measurement_processor: Optional[queue.Queue] = None
        self._to_stream_q: Optional[queue.Queue] = None

        super().__init__(*args, **kwargs)

    def __call__(
        self,
        commands_from_api: queue.Queue[Any],
        responses_to_api: queue.Queue[Any],
        uavs_to_measurement_processor: queue.Queue[Any],
        to_stream_q: Optional[queue.Queue],
        *args,
        **kwargs,
    ) -> None:
        self._app = self._db.get_app_instance()
        self._incoming_command_q = commands_from_api
        self._outgoing_responses_q = responses_to_api
        self._uavs_to_measurement_processor = uavs_to_measurement_processor
        self._to_stream_q = to_stream_q
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
                uav_entity, self._uavs_to_measurement_processor, self._to_stream_q, self._logger.level
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

    def _handle_commands(self):
        """Thread to handle incoming commands, and forward them to the UAVConnectionHandler with the correct id"""
        while True:
            # get commands
            try:
                target_id, command = self._incoming_command_q.get(timeout=0.2)
            except queue.Empty:
                continue

            self._logger.info(
                f"Forwarding command '{proto_cmd.Instruction.Name(command.instruction)}' to { f'uav_id #{target_id}' if target_id else 'all connected devices'}"
            )

            # send commands using UAVConnectionHandlers
            response = None
            try:
                # TODO: only target UAVs we're connected to, exclude those that we're trying to connect to
                if target_id == 0:  # id==0 -> send to all connected uavs
                    target_uav_list = self._uavs.values()
                else:
                    target_uav_list = [self._uavs[target_id]]
            except KeyError:
                emsg = f"No uav with id {target_id} connected"
                response = proto_cmd.Response(
                    error=proto_cmd.CommandError(description=emsg)
                )
                self._logger.warning(f"Command destination error: {emsg}")
            else:
                # TODO: RuntimeError: dictionary changed size during iteration -> we need to lock the target list??
                for uav in target_uav_list:
                    response = uav.send_command(command)
                    self._logger.trace(
                        f"Got response for command '{proto_cmd.Instruction.Name(command.instruction)}' from uav_id #{uav.id}: {response}"
                    )

            # TODO: aggregate responses for commands sent to all UAVs
            if response is None:
                emsg = f"No answer for command"
                response = proto_cmd.Response(
                    error=proto_cmd.CommandError(description=emsg)
                )
            # send the response
            # TODO: timeou, check queue full exception???
            self._outgoing_responses_q.put(response)

    def _pre_loop(self):
        """
        Setup a thread managing commands
        """
        # Start command handler thread
        cmd_thread = threading.Thread(target=self._handle_commands)
        cmd_thread.daemon = True
        cmd_thread.start()

    def _loop(self) -> None:
        self._refresh_active_sensor_list()
        time.sleep(1)
