from __future__ import annotations
from multiprocessing.managers import DictProxy
import pickle
import queue
from queue import Queue

import subprocess
import shlex
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
    ]

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._cmd_timeout_seconds = 30.0
        self.config_id = 0
        self._comm_queue_in: Optional[Queue] = None
        self._comm_queue_out: Optional[Queue] = None
        self._cs_queue_in: Optional[Queue] = None
        self._cs_queue_out: Optional[Queue] = None
        self._stream_conf_queue_out: Optional[Queue] = None
        self._latest_telemetry_proxy: Optional[DictProxy] = None

    def __call__(
        self,
        comm_queue_in: Queue[Any],
        comm_queue_out: Queue[Any],
        cs_queue_in: Queue[str],
        cs_queue_out: Queue[str],
        stream_conf_queue_out: Queue[Any],
        latest_telemetry_proxy: Optional[DictProxy] = None,
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_in = comm_queue_in
        self._comm_queue_out = comm_queue_out
        self._cs_queue_in = cs_queue_in
        self._cs_queue_out = cs_queue_out
        self._stream_conf_queue_out = stream_conf_queue_out
        self._latest_telemetry_proxy = latest_telemetry_proxy
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
            response.id = command.id
            response.instruction = command.instruction
            response.error.description = f"CS not responding"
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
                if command.HasField("parameter"):
                    self._config(response, command.config)
                else:
                    self._config(response, None)

            case proto_cmd.TELEMETRY:
                self._telemetry(response)

            case proto_cmd.INFO:
                self._info(response)

            case proto_cmd.POSITION:
                # Check whether command is a query or a setting
                if command.HasField("parameter"):
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
            case _:
                response.error.description = "Unknown command"

        # Send response to Communicator
        return response  # .SerializeToString()

    def _cs_execute(
        self, command: str, timeout: Optional[float] = None
    ) -> Optional[list[str]]:
        """Send a list of commands to CoreService, return the result."""
        assert self._cs_queue_in is not None
        assert self._cs_queue_out is not None
        if timeout is None:
            timeout = self._cmd_timeout_seconds
        if command[-1:] != ";":
            command += ";"
        self._cs_queue_out.put(command)
        try:
            response = self._cs_queue_in.get(timeout=timeout)

            if response is None:
                return None
            response = response.strip("\r\n\t ;")
            response_parts = shlex.split(response)
            error_code = int(response_parts[0])
            if error_code > 0:
                self._logger.warning(f"Error {response} for cmd {command}")
            return response_parts
        except queue.Empty:
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

    def _config(
        self, response: proto_cmd.Response, config: proto_cmd.Config | None
    ) -> None:
        """Set of query system configuration"""
        if config is not None:
            for config_command, proto_lambda in self._CONFIG_COMMANDS:
                command_arg = proto_lambda(config)
                if not command_arg:
                    continue
                cs_command = config_command.format(command_arg)
                cs_response = self._cs_execute(cs_command)
                if cs_response is not None:
                    error_code = int(cs_response[0])
                    if error_code != 0:
                        self._logger.error(f"Cannot set {cs_command}")
                        raise CSErrorException(error_code, cs_response[1])
                    else:
                        self.config_id += 1
                else:
                    response.error.description = "CoreService not responding"
                    raise CSTimeoutException()
        # try:
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
