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
from pysagax.field.loop import Loop


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

    # CoreService commands matching protobuf Instructions
    _CS_COMMANDS = {
        proto_cmd.PING: "CORE:Ping! {value}",
        proto_cmd.POSITION: "SOURCE:Position{mode} {value}",
        proto_cmd.SOURCE_START: "SOURCE:Start!",
        proto_cmd.SOURCE_STOP: "SOURCE:Stop!",
        proto_cmd.REC_START: "RECORDING:Start!",
        proto_cmd.REC_STOP: "RECORDING:Stop!",
    }
    _CONFIG_COMMANDS = [
        ("SOURCE:Path! {};", lambda config: config.source_path),
        ("SOURCE:CenterFrequency! {:.0f};", lambda config: config.center_frequency),
        ("SOURCE:IqRate! {};", lambda config: config.iq_rate),
        ("SOURCE:BurstStride! {};", lambda config: config.burst_stride),
        ("SOURCE:PlaybackSpeed! {:.2f};", lambda config: config.playback_speed),
        (
            "SOURCE:ChannelGain! 0 {};",
            lambda config: (
                config.channel_gain[0] if len(config.channel_gain) >= 1 else 0
            ),
        ),
        (
            "SOURCE:ChannelGain! 1 {};",
            lambda config: (
                config.channel_gain[1] if len(config.channel_gain) >= 2 else 0
            ),
        ),
        (
            "SOURCE:ChannelGain! 2 {};",
            lambda config: (
                config.channel_gain[2] if len(config.channel_gain) >= 3 else 0
            ),
        ),
        (
            "SOURCE:ChannelGain! 3 {};",
            lambda config: (
                config.channel_gain[3] if len(config.channel_gain) >= 4 else 0
            ),
        ),
        ("SOURCE:Configure!;", lambda config: " "),
        ("AOA:BinCount! {};", lambda config: config.bin_count),
        ("AOA:Configure!;", lambda config: " "),
        ("ROI:Enable! {};", lambda config: "1" if len(config.roi) else "0"),
        (
            "ROI:CenterFrequency! {:.0f};",
            lambda config: (config.roi[0].center_frequency if len(config.roi) else 0.0),
        ),
        (
            "ROI:Span! {:.0f};",
            lambda config: config.roi[0].span if len(config.roi) else 0.0,
        ),
        (
            "ROI:Threshold! {:.0f};",
            lambda config: config.roi[0].threshold if len(config.roi) else 0.0,
        ),
        ("ROI:Configure!;", lambda config: " "),
    ]

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
            case proto_cmd.CS_PING:
                self._cs_ping(response, command.ping_data)

            case proto_cmd.CONFIG:
                # Check whether command is a query or a setting
                if (
                    command.HasField("parameter")
                    or command.kind == proto_cmd.Command.WRITE
                ) and command.kind != proto_cmd.Command.READ:
                    conf_thread = threading.Thread(
                        target=self._config_set, args=(response, command.config)
                    )
                    conf_thread.start()
                    response.success = True
                    # self._config(response, command.config)
                else:
                    self._config(response)

            case proto_cmd.TELEMETRY:
                self._telemetry(response)

            case proto_cmd.INFO:
                self._info(response)

            case proto_cmd.POSITION:
                # Check whether command is a query or a setting
                if (
                    command.HasField("parameter")
                    or command.kind == proto_cmd.Command.WRITE
                ) and command.kind != proto_cmd.Command.READ:
                    self._position(response, command.position)
                else:
                    self._position(response, None)

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
            ):
                self._cs_control(response, command.instruction)  # type: ignore
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

    def _cs_execute(
        self, command: str, timeout: Optional[float] = None, important: bool = False
    ) -> Optional[list[str]]:
        """Send a list of commands to CoreService, return the result."""
        assert self._cs_queue_in is not None
        assert self._cs_queue_out is not None
        assert self._cs_lock is not None
        if timeout is None:
            timeout = self._cmd_timeout_seconds
        if command[-1:] != ";":
            command += ";"
        if self._cs_lock.locked() and not important:
            raise CSThreadOccupied(self._currently_running_cs_command)
        with self._cs_lock:
            self._cs_queue_out.put(command)
            self._currently_running_cs_command = command
            try:
                command_recv = ""
                response: Optional[str] = None
                while command_recv.strip("\r\n\t ;") != command.strip("\r\n\t ;"):
                    command_recv, response = self._cs_queue_in.get(timeout=timeout)

                if response is None:
                    return None
                response = response.strip("\r\n\t ;")
                response_parts = shlex.split(response)
                error_code = int(response_parts[0])
                if error_code > 0:
                    self._logger.warning(f"Error {response} for cmd {command}")
                self._currently_running_cs_command = ""
                return response_parts
            except queue.Empty:
                self._currently_running_cs_command = ""
                return None

    def _cs_ping(self, response: proto_cmd.Response, ping_data: str) -> None:
        """Send a Ping command to CoreService"""

        # Generate and execute appropriate CoreService command
        cs_command = self._CS_COMMANDS[proto_cmd.PING].format(value=ping_data)
        cs_response = self._cs_execute(cs_command, timeout=1.0)

        # Check for response validity
        if cs_response is not None:
            response.ping_data = cs_response[1]
        else:
            response.error.description = "CoreService not responding"

    def _cs_query(self, query_cmd: str) -> Optional[str]:
        cs_response = self._cs_execute(query_cmd)
        if cs_response is not None:
            error_code = int(cs_response[0])
            if error_code == 0:
                return cs_response[1]
            self._logger.warning(
                f"Could not query {query_cmd}, CS{error_code}{cs_response[1]}"
            )
            return None
        raise CSTimeoutException()

    def _cs_query_multiple(self, query_cmd: str) -> Optional[str]:
        cs_response = self._cs_execute(query_cmd)
        if cs_response is not None:
            error_code = int(cs_response[0])
            if error_code == 0:
                return " ".join(cs_response[1:])
            self._logger.warning(
                f"Could not query {query_cmd}, CS{error_code}{cs_response[1]}"
            )
            return None
        raise CSTimeoutException()

    def _config_set(
        self, response: proto_cmd.Response, config: proto_cmd.Config
    ) -> None:
        """Set system configuration"""
        self._config_status_message = proto_cmd.ConfigStatus()
        self._config_status_message.start_time.GetCurrentTime()
        for config_command, proto_lambda in self._CONFIG_COMMANDS:
            command_arg = proto_lambda(config)
            if not command_arg:
                continue
            self._config_status_message.queue.append(
                str(config_command.format(command_arg))
            )

        for config_command, proto_lambda in self._CONFIG_COMMANDS:
            command_arg = proto_lambda(config)
            if not command_arg:
                continue
            cs_command = config_command.format(command_arg)
            cs_response = self._cs_execute(cs_command, important=True, timeout=30.0)
            self._config_status_message.success = True

            if cs_response is not None:
                self._config_status_message.responses[cs_command] = "; ".join(
                    cs_response
                )
                error_code = int(cs_response[0])
                if error_code != 0:
                    self._logger.error(f"Cannot set {cs_command}")
                    # try to set the remaining values
                    # raise CSErrorException(error_code, cs_response[1])
                    self._config_status_message.error_code = error_code
                    self._config_status_message.error_description = (
                        cs_response[1] if len(cs_response) > 1 else "Unknown"
                    )
                    self._config_status_message.success = False
                else:
                    self.config_id += 1
                    if self._latest_config_id_value is not None:
                        self._latest_config_id_value.set(self.config_id)
            else:
                self._config_status_message.responses[command_arg] = "TIMED OUT"
                self._config_status_message.error_code = -1

                response.error.description = "CoreService not responding"
                self._logger.error(f"Config timed out on command {cs_command}")
                # raise CSTimeoutException()
        self._logger.info("Configuration finished")
        self._config_status_message.finish_time.GetCurrentTime()

    def _config(self, response: proto_cmd.Response) -> None:
        """Query system configuration"""
        defaults = lambda val, defa: defa if val is None else val
        response.config.config_id = self.config_id
        response.config.center_frequency = float(
            defaults(self._cs_query("SOURCE:CenterFrequency?;"), 0)
        )
        response.config.iq_rate = int(
            float(defaults(self._cs_query("SOURCE:IqRate?;"), 0))
        )
        response.config.playback_speed = float(
            defaults(self._cs_query("SOURCE:PlaybackSpeed?;"), 0)
        )
        response.config.bin_count = int(defaults(self._cs_query("AOA:BinCount?;"), 0))
        response.config.burst_stride = int(
            defaults(self._cs_query("SOURCE:BurstStride?;"), 0)
        )
        for gain_index in range(4):
            response.config.channel_gain.append(
                int(
                    float(
                        defaults(
                            self._cs_query(f"SOURCE:ChannelGain? {gain_index};"), 0
                        )
                    )
                )
            )
        response.config.source_path = defaults(
            self._cs_query_multiple("SOURCE:Path?;"), "UNKNOWN"
        )
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

    def _position(self, response: proto_cmd.Response, position: int | None) -> None:
        """Set or query source position"""

        # Generate and execute appropriate CoreService command
        if position is not None:
            cs_command = self._CS_COMMANDS[proto_cmd.POSITION].format(
                mode="!", value=position
            )
        else:
            cs_command = self._CS_COMMANDS[proto_cmd.POSITION].format(
                mode="?", value=""
            )
        cs_response = self._cs_execute(cs_command)

        # Check for response validity
        if cs_response is not None:
            error_code = int(cs_response[0])
            if error_code == 0:
                if cs_response[1].isdigit():
                    response.position = int(cs_response[1])
                    return
                elif position is not None:
                    response.position = position
                    return
            raise CSErrorException(error_code, cs_response[1])
        else:
            raise CSTimeoutException()

    def _cs_control(
        self, response: proto_cmd.Response, instruction: proto_cmd.Instruction
    ) -> None:
        """Send control commands (no parameters) to CoreService"""

        # Obtain appropriate CoreService command
        cs_command = self._CS_COMMANDS[instruction]  # type: ignore
        cs_response = self._cs_execute(cs_command)

        # Check for response validity
        # Check for response validity
        if cs_response is not None:
            error_code = int(cs_response[0])
            if error_code == 0:
                # TODO: Check cs_response for success
                response.success = True
            else:
                response.success = False
                raise CSErrorException(error_code, cs_response[1])
        else:
            response.success = False
            raise CSTimeoutException()
