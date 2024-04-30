from __future__ import annotations
from multiprocessing.managers import DictProxy, ValueProxy
import pickle
import queue
from queue import Queue

import subprocess
import shlex
import threading
from typing import Any, Optional

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading
from pysagax.common.loop import Loop


class CSErrorException(Exception):
    def __init__(self, error_code: int, error_description: str, *args: object) -> None:
        super().__init__(*args)
        self.error_code = error_code
        self.error_description = error_description


class CSTimeoutException(Exception):
    pass


class CSThreadOccupied(Exception):
    def __init__(self, running_command: str, *args: object) -> None:
        super().__init__(*args)
        self.running_command = running_command


class Interpreter(Loop):
    """Main coordinator process for the sensor software stack"""

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._cmd_timeout_seconds = 1.0
        self.config_id = 0
        self._comm_queue_in: Optional[Queue] = None
        self._comm_queue_out: Optional[Queue] = None
        self._cs_queue_in: Optional[Queue] = None
        self._cs_queue_out: Optional[Queue] = None
        self._stream_conf_queue_out: Optional[Queue] = None
        self._heading_conf_queue_out: Optional[Queue] = None
        self._postproc_conf_queue_out: Optional[Queue] = None
        self._postproc_conf_queue_resp_in: Optional[Queue] = None
        self._latest_telemetry_proxy: Optional[DictProxy] = None
        self._cs_lock: Optional[threading.Lock] = None
        self._currently_running_cs_command = ""
        self._config_status_message: Optional[proto_cmd.ConfigStatus] = None
        self._latest_config_id_value: Optional[ValueProxy[int]] = None

    def __call__(
        self,
        comm_queue_in: Queue[Any],
        comm_queue_out: Queue[Any],
        cs_queue_in: Queue[str],
        cs_queue_out: Queue[str],
        stream_conf_queue_out: Queue[Any],
        heading_conf_queue_out: Queue[Any],
        postproc_conf_queue_out: Queue[Any],
        postproc_conf_queue_resp_in: Queue[Any],
        latest_telemetry_proxy: Optional[DictProxy] = None,
        latest_config_id_value: Optional[ValueProxy[int]] = None,
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_in = comm_queue_in
        self._comm_queue_out = comm_queue_out
        self._cs_queue_in = cs_queue_in
        self._cs_queue_out = cs_queue_out
        self._stream_conf_queue_out = stream_conf_queue_out
        self._heading_conf_queue_out = heading_conf_queue_out
        self._postproc_conf_queue_out = postproc_conf_queue_out
        self._postproc_conf_queue_resp_in = postproc_conf_queue_resp_in
        self._latest_telemetry_proxy = latest_telemetry_proxy
        self._latest_config_id_value = latest_config_id_value
        self._cs_lock = threading.Lock()
        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        assert self._comm_queue_in is not None
        assert self._comm_queue_out is not None
        assert self._cs_queue_in is not None
        assert self._cs_queue_out is not None
        # Hang until a new command is received
        command = self._comm_queue_in.get()
        response = proto_cmd.Response()
        # Execute command
        try:
            response = self._process(command)
        except CSErrorException as cs_err:
            response.id = command.id
            response.instruction = command.instruction
            response.error.description = (
                f"CS{cs_err.error_code}: {cs_err.error_description}"
            )
        except CSTimeoutException:
            self._logger.error("CS not responding")
            response.id = command.id
            response.instruction = command.instruction
            response.error.description = f"CS not responding"
        except CSThreadOccupied as cs_occ:
            self._logger.error(f"CS is occupied by command {cs_occ.running_command}")
            response.id = command.id
            response.instruction = command.instruction
            response.error.description = (
                f"CS is occupied by command {cs_occ.running_command}"
            )
        # Send response to Communicator
        self._comm_queue_out.put(response)

    def _process(self, command: Any) -> proto_cmd.Response:
        """Interpret, route and execute incoming commands"""

        # Parse command to Protobuf format
        assert isinstance(command, proto_cmd.Command)
        # command = proto.Command()
        # command.ParseFromString(raw_command)
        self._logger.debug(
            f"Instruction: {proto_cmd.Instruction.Name(command.instruction)}"
        )

        # Prepare appropriate response
        response = proto_cmd.Response()
        response.id = command.id
        response.instruction = command.instruction

        # Route command based on the given Instruction
        #   response is always passed as a reference
        match command.instruction:
            case proto_cmd.PING:
                response.ping_data = command.ping_data
            case proto_cmd.CONFIG:
                # Check whether command is a query or a setting
                if (
                    command.HasField("parameter")
                    or command.kind == proto_cmd.Command.WRITE
                ) and command.kind != proto_cmd.Command.READ:
                    if command.config.HasField("heading"):  # Heading part is set
                        assert self._heading_conf_queue_out is not None
                        self._heading_conf_queue_out.put(command.config.heading)
                    if command.config.HasField("cs"):
                        cs_command = proto_cmd.Command()
                        cs_command.CopyFrom(command)
                        cs_command.kind = proto_cmd.Command.WRITE
                        cs_resp = self._cs_control(cs_command, timeout_ms=30000)
                        if cs_resp.HasField("error"):
                            response.error.CopyFrom(cs_resp.error)
                        else:
                            response.config.cs.CopyFrom(cs_resp.config.cs)

                    else:
                        self._config_status_message = proto_cmd.ConfigStatus()
                        self._config_status_message.start_time.GetCurrentTime()
                        self._config_status_message.finish_time.GetCurrentTime()
                    response.success = True
                    # self._config(response, command.config)
                else:
                    self._config(response)

            case proto_cmd.TELEMETRY:
                self._telemetry(response)

            case proto_cmd.INFO:
                self._info(response)

            case proto_cmd.CS_START:
                subprocess.run(["sudo", "StartCoreService"])

            case proto_cmd.CS_STOP:
                subprocess.run(["sudo", "StopCoreService"])

            case proto_cmd.CS_RESTART:
                subprocess.run(["sudo", "StopCoreService"])
                subprocess.run(["sudo", "StartCoreService"])

            case proto_cmd.HEADING_START:
                response.error.description = "Not yet implemented"

            case proto_cmd.HEADING_STOP:
                response.error.description = "Not yet implemented"

            case (
                proto_cmd.SOURCE_START
                | proto_cmd.SOURCE_STOP
                | proto_cmd.REC_START
                | proto_cmd.REC_STOP
                | proto_cmd.CS_PING
                | proto_cmd.POSITION
            ):
                response.CopyFrom(self._cs_control(command))
            case proto_cmd.STREAM_START | proto_cmd.STREAM_STOP:
                assert self._stream_conf_queue_out is not None
                self._stream_conf_queue_out.put(command)
            case proto_cmd.CONFIG_STATUS:
                if self._config_status_message is None:
                    response.error.description = "No available config status"
                else:
                    response.config_status.CopyFrom(self._config_status_message)
            case _:
                response.error.description = "Unknown command"

        # Send response to Communicator
        return response  # .SerializeToString()

    def _postproc_configure(self, command: Any) -> Any:
        assert self._postproc_conf_queue_out is not None
        assert self._postproc_conf_queue_resp_in is not None
        self._postproc_conf_queue_out.put(command)
        try:
            return self._postproc_conf_queue_resp_in.get(timeout=5)
        except queue.Empty:
            # Postproc module does not respond
            return None

    def _config(self, response: proto_cmd.Response) -> None:
        """Query system configuration"""

        cs_query_cmd = proto_cmd.Command()
        cs_query_cmd.instruction = proto_cmd.CONFIG
        cs_query_cmd.kind = proto_cmd.Command.READ
        cs_query_resp = self._cs_control(cs_query_cmd)
        response.config.cs.CopyFrom(cs_query_resp.config.cs)
        if (
            self._latest_telemetry_proxy is None
            or "HeadingStatus" not in self._latest_telemetry_proxy
        ):
            response.config.heading.selected_source_type = "Unknown"
        else:
            heading_status_object: proto_heading.HeadingStatus = pickle.loads(
                self._latest_telemetry_proxy["HeadingStatus"]
            )
            response.config.heading.selected_source_type = (
                heading_status_object.selected_source_type
            )
            for param in heading_status_object.parameters:
                response.config.heading.parameters[param.name] = param.value

        # TODO no ROI query methods implemented in CS

        # except ValueError:
        #    response.error.description = "Invalid config on query"

    def _telemetry(self, response: proto_cmd.Response) -> None:
        """Query system telemetry"""
        if (
            self._latest_telemetry_proxy is None
            or "Telemetry" not in self._latest_telemetry_proxy
        ):
            response.error.description = "Telemetry not available"
            return
        telemetry_object: proto_data.Telemetry = pickle.loads(
            self._latest_telemetry_proxy["Telemetry"]
        )
        response.telemetry.MergeFrom(telemetry_object)

    def _info(self, response: proto_cmd.Response) -> None:
        """Query system info"""
        if (
            self._latest_telemetry_proxy is None
            or "SystemInfo" not in self._latest_telemetry_proxy
        ):
            response.error.description = "SystemInfo not available"
            return
        system_info_object: proto_cmd.SystemInfo = pickle.loads(
            self._latest_telemetry_proxy["SystemInfo"]
        )
        response.info.MergeFrom(system_info_object)

    def _cs_control(
        self, command: proto_cmd.Command, timeout_ms: int = 200
    ) -> proto_cmd.Response:
        """Send control commands (no parameters) to CoreService"""
        assert self._cs_queue_in is not None
        assert self._cs_queue_out is not None

        # Obtain appropriate CoreService command
        cs_command = proto_cmd.Command()
        cs_command.CopyFrom(command)
        if cs_command.HasField("config"):
            cs_command.config.Clear()
            cs_command.config.cs.CopyFrom(command.config.cs)
        self._cs_queue_out.put((cs_command, timeout_ms))
        cs_response = self._cs_queue_in.get()
        if cs_response is not None:
            return cs_response
        else:
            raise CSTimeoutException()
