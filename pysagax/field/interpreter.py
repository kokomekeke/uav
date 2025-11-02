from __future__ import annotations
from multiprocessing.managers import DictProxy, ValueProxy
import pickle
import queue
from queue import Queue

import subprocess
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
        self._se_queue_in: Optional[Queue] = None
        self._se_queue_out: Optional[Queue] = None
        self._stream_conf_queue_out: Optional[Queue] = None
        self._heading_conf_queue_out: Optional[Queue] = None
        self._postproc_conf_queue_out: Optional[Queue] = None
        self._postproc_conf_queue_resp_in: Optional[Queue] = None
        self._latest_se_proxy: Optional[DictProxy] = None
        self._latest_telemetry_proxy: Optional[DictProxy] = None
        self._currently_running_cs_command = ""
        self._config_status_message: Optional[proto_cmd.ConfigStatus] = None
        self._latest_config_id_value: Optional[ValueProxy[int]] = None
        self._apm_communicator_messages_q: Optional[Queue] = None
        self._apm_communicator_responses_q: Optional[Queue] = None

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
        apm_communicator_messages_q: Queue[Any],
        apm_communicator_responses_q: Queue[Any],
        latest_se_proxy: Optional[DictProxy] = None,
        latest_telemetry_proxy: Optional[DictProxy] = None,
        latest_config_id_value: Optional[ValueProxy[int]] = None,
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_in = comm_queue_in
        self._comm_queue_out = comm_queue_out
        self._se_queue_in = cs_queue_in
        self._se_queue_out = cs_queue_out
        self._stream_conf_queue_out = stream_conf_queue_out
        self._heading_conf_queue_out = heading_conf_queue_out
        self._postproc_conf_queue_out = postproc_conf_queue_out
        self._postproc_conf_queue_resp_in = postproc_conf_queue_resp_in
        self._apm_communicator_messages_q = apm_communicator_messages_q
        self._apm_communicator_responses_q = apm_communicator_responses_q
        self._latest_se_proxy = latest_se_proxy
        self._latest_telemetry_proxy = latest_telemetry_proxy
        self._latest_config_id_value = latest_config_id_value
        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        assert self._comm_queue_in is not None
        assert self._comm_queue_out is not None
        assert self._se_queue_in is not None
        assert self._se_queue_out is not None
        # Hang until a new command is received
        command = self._comm_queue_in.get()
        response = proto_cmd.Response()
        # Execute command
        try:
            response = self._process(command)
        except CSErrorException as cs_err:
            msg = f"CS{cs_err.error_code}: {cs_err.error_description}"
            self._logger.error(msg)
            response.error.description = msg
        except CSTimeoutException:
            self._logger.error("CS not responding")
            response.error.description = f"CS not responding"
        except CSThreadOccupied as cs_occ:
            msg = f"CS is occupied by command {cs_occ.running_command}"
            self._logger.error(msg)
            response.error.description = msg
        except queue.Empty:
            # Works for those commands that wait for an answer on a queue from the target module
            # TODO: check _process() so that no command has a response with possibly infinite wait time (eg in_queue.get witout timeout)
            msg = f"The target module didn't answer on time for the command\n{command}"
            self._logger.critical(msg)
            response.error.description = msg
        except queue.Full:
            # TODO: check _process() so that no command has a response with possibly infinite wait time (eg in_queue.put witout timeout)
            msg = f"The target module's command queue is full."
            self._logger.critical(msg)
            response.error.description = msg
        finally:
            # The response should contain the id and instruction of the comman
            response.id = command.id
            response.instruction = command.instruction

        # Send response to Communicator
        self._comm_queue_out.put(response)  # should use util.queue_put?

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

        # Route command based on the given Instruction
        #   response is always passed as a reference
        match command.instruction:
            case proto_cmd.PING:
                response.ping_data = command.ping_data

            case proto_cmd.CONFIG:
                self._process_config_command(command, response)

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
                | proto_cmd.CS_CALIBRATE_START
                | proto_cmd.CS_CALIBRATE_ABORT
                | proto_cmd.CS_SCAN_START
                | proto_cmd.CS_TURN_OFF_COMPENSATION
                | proto_cmd.CS_TURN_ON_COMPENSATION
                | proto_cmd.CS_READ_PHASEDIFFS_FROM_FILE
                | proto_cmd.CS_CALIBRATION_VALUES_QUERY
                | proto_cmd.CS_CALIBRATION_PHASE_CHECK
                | proto_cmd.AUTO_CALIBRATION_ENABLE
                | proto_cmd.AUTO_CALIBRATION_DISABLE
                | proto_cmd.AUTO_CALIBRATION_TRIGGER
                | proto_cmd.CS_RELOAD_CONFIG
                | proto_cmd.CS_ACTIVATE_DEMODULATION
                | proto_cmd.CS_DEACTIVATE_DEMODULATION
                | proto_cmd.CS_START_DEMODULATION_RECORD
                | proto_cmd.CS_STOP_DEMODULATION_RECORD
            ):
                response.CopyFrom(self._se_control(command))

            case proto_cmd.STREAM_START | proto_cmd.STREAM_STOP:
                assert self._stream_conf_queue_out is not None
                self._stream_conf_queue_out.put(command)  # should use util.queue_put?

            case proto_cmd.CONFIG_STATUS:
                if self._config_status_message is None:
                    response.error.description = "No available config status"
                else:
                    response.config_status.CopyFrom(self._config_status_message)
            case proto_cmd.FORWARD_TO_APM:
                response.MergeFrom(self._apm_control(command))
            case _:
                response.error.description = "Unknown command"

        # Send response to Communicator
        return response  # .SerializeToString()

    def _process_config_command(
        self, command: proto_cmd.Command, response: proto_cmd.Response
    ) -> None:
        """
        Processes CONFIG commands, and modifies the given response based on the
        responses from the related modules
        """
        # Check whether command is a query or a setting
        if command.kind == proto_cmd.Command.READ or not (
            command.HasField("parameter") or command.kind == proto_cmd.Command.WRITE
        ):
            # querying current state
            self._config(response)
            return

        # Setting new config:

        response.success = True
        if command.config.HasField("heading"):  # Heading part is set
            assert self._heading_conf_queue_out is not None
            self._heading_conf_queue_out.put(
                command.config.heading
            )  # should use util.queue_put?

        if command.config.HasField("cs") or command.config.HasField("se"):
            assert self._se_queue_in is not None and self._se_queue_out is not None
            self._se_queue_out.put(command)  # should use util.queue_put?
            se_response = self._se_queue_in.get()
            if se_response.HasField("error"):
                response.error.CopyFrom(se_response.error)
                response.success = False
            else:
                response.config.cs.CopyFrom(se_response.config.cs)
                response.config.se.CopyFrom(se_response.config.se)
        else:
            self._config_status_message = proto_cmd.ConfigStatus()
            self._config_status_message.start_time.GetCurrentTime()
            self._config_status_message.finish_time.GetCurrentTime()

        if command.config.HasField("pp"):
            pp_response = self._postproc_configure(command)
            if pp_response is not None:
                if pp_response.HasField("error"):
                    response.error.CopyFrom(pp_response.error)
                    response.success = False
                else:
                    response.config.pp.CopyFrom(pp_response.config.pp)
        # self._config(response, command.config)

    def _postproc_configure(self, command: Any) -> Any:
        assert self._postproc_conf_queue_out is not None
        assert self._postproc_conf_queue_resp_in is not None
        self._postproc_conf_queue_out.put(command)  # should use util.queue_put?
        try:
            return self._postproc_conf_queue_resp_in.get(timeout=5)
        except queue.Empty:
            # Postproc module does not respond
            return None

    def _config(self, response: proto_cmd.Response) -> None:
        """Query system configuration"""
        if self._latest_se_proxy is not None and "config" in self._latest_se_proxy:
            se_config: proto_cmd.ScanEngineConfig = self._latest_se_proxy["config"]
            response.config.se.CopyFrom(se_config)
        if self._latest_se_proxy is not None and "cs_config" in self._latest_se_proxy:
            cs_config: proto_cmd.CoreServiceConfig = self._latest_se_proxy["cs_config"]
            response.config.cs.CopyFrom(cs_config)
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

    def _se_control(self, command: proto_cmd.Command) -> proto_cmd.Response:
        assert self._se_queue_in is not None and self._se_queue_out is not None
        self._se_queue_out.put(command)  # should use util.queue_put? or timeout
        # TODO: timeout needed. If cs is not connected we indefinitely wait here for example for a response to a CS_PING
        return self._se_queue_in.get()

    def _apm_control(self, command: proto_cmd.Command) -> proto_cmd.Response:
        """Route packets to APMCommunicator (Aviation Processing Module of the Altiss  project)"""
        self._apm_communicator_messages_q.put(command, timeout=0.1)
        return self._apm_communicator_responses_q.get(timeout=1)
