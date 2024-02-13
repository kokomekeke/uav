from __future__ import annotations
import queue
from queue import Queue

import shlex
from typing import Any, Optional

import pysagax.message.command_pb2 as proto
from pysagax.field.loop import Loop


class Interpreter(Loop):
    """Main coordinator process for the sensor software stack"""

    # CoreService commands matching protobuf Instructions
    _CS_COMMANDS = {
        proto.PING: "CORE:Ping! {value}",
        proto.POSITION: "SOURCE:Position{mode} {value}",
        proto.SOURCE_START: "SOURCE:Start!",
        proto.SOURCE_STOP: "SOURCE:Stop!",
        proto.REC_START: "RECORDING:Start!",
        proto.REC_STOP: "RECORDING:Stop!",
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
                config.channel_gain[1] if len(config.channel_gain) >= 1 else 0
            ),
        ),
        (
            "SOURCE:ChannelGain! 2 {};",
            lambda config: (
                config.channel_gain[2] if len(config.channel_gain) >= 1 else 0
            ),
        ),
        (
            "SOURCE:ChannelGain! 3 {};",
            lambda config: (
                config.channel_gain[3] if len(config.channel_gain) >= 1 else 0
            ),
        ),
        ("SOURCE:Configure!;", lambda config: ""),
        ("AOA:BinCount! {};", lambda config: config.bin_count),
        ("AOA:Configure!;", lambda config: ""),
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

    def __call__(
        self,
        comm_queue_in: Queue[Any],
        comm_queue_out: Queue[Any],
        cs_queue_in: Queue[str],
        cs_queue_out: Queue[str],
        *args,
        **kwargs,
    ) -> None:
        self._comm_queue_in = comm_queue_in
        self._comm_queue_out = comm_queue_out
        self._cs_queue_in = cs_queue_in
        self._cs_queue_out = cs_queue_out

        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        # Hang until a new command is received
        command = self._comm_queue_in.get()

        # Execute command
        response = self._process(command)

        # Send response to Communicator
        self._comm_queue_out.put(response)

    def _process(self, raw_command: bytes) -> bytes:
        """Interpret, route and execute incoming commands"""

        # Parse command to Protobuf format
        command = proto.Command()
        command.ParseFromString(raw_command)
        self._logger.debug(
            f"Instruction: {proto.Instruction.Name(command.instruction)}"
        )

        # Prepare appropriate response
        response = proto.Response()
        response.id = command.id
        response.instruction = command.instruction

        # Route command based on the given Instruction
        #   response is always passed as a reference
        match command.instruction:
            case proto.PING:
                self._ping(response, command.ping_data)

            case proto.CONFIG:
                # Check whether command is a query or a setting
                if command.HasField("parameter"):
                    self._config(response, command.config)
                else:
                    self._config(response, None)

            case proto.TELEMETRY:
                self._telemetry(response)

            case proto.INFO:
                self._info(response)

            case proto.POSITION:
                # Check whether command is a query or a setting
                if command.HasField("parameter"):
                    self._position(response, command.position)
                else:
                    self._position(response, None)

            case proto.CS_START:
                pass

            case proto.CS_STOP:
                pass

            case proto.CS_RESTART:
                pass

            case proto.HEADING_START:
                pass

            case proto.HEADING_STOP:
                pass

            case (
                proto.SOURCE_START
                | proto.SOURCE_STOP
                | proto.REC_START
                | proto.REC_STOP
            ):
                self._cs_control(response, command.instruction)

            case _:
                response.error.description = "Unknown command"

        # Send response to Communicator
        return response.SerializeToString()

    def _cs_execute(self, command: str) -> Optional[list[str]]:
        """Send a list of commands to CoreService, return the result."""

        if command[-1:] != ";":
            command += ";"
        self._cs_queue_out.put(command)
        try:
            response = self._cs_queue_in.get(timeout=self._cmd_timeout_seconds)

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

    def _ping(self, response: proto.Response, ping_data: str) -> None:
        """Send a Ping command to CoreService"""

        # Generate and execute appropriate CoreService command
        cs_command = self._CS_COMMANDS[proto.PING].format(value=ping_data)
        cs_response = self._cs_execute(cs_command)

        # Check for response validity
        if cs_response is not None:
            response.ping_data = cs_response[1]
        else:
            response.error.description = "CoreService not responding"

    def _cs_query(self, query_cmd: str) -> str:
        cs_response = self._cs_execute(query_cmd)
        if cs_response is not None:
            error_code = int(cs_response[0])
            if error_code == 0:
                return cs_response[1]
        return ""

    def _cs_query_multiple(self, query_cmd: str) -> str:
        cs_response = self._cs_execute(query_cmd)
        if cs_response is not None:
            error_code = int(cs_response[0])
            if error_code == 0:
                return " ".join(cs_response[1:])
        return ""

    def _config(self, response: proto.Response, config: proto.Config | None) -> None:
        """Set of query system configuration"""
        if config is not None:
            for config_command, proto_lambda in self._CONFIG_COMMANDS:
                cs_command = config_command.format(proto_lambda(config))
                cs_response = self._cs_execute(cs_command)
                if cs_response is not None:
                    error_code = int(cs_response[0])
                    if error_code != 0:
                        self._logger.error(f"Cannot set {cs_command}")
                    else:
                        self.config_id += 1
                else:
                    response.error.description = "CoreService not responding"
                    return
        # try:
        response.config.config_id = self.config_id
        response.config.center_frequency = float(
            self._cs_query("SOURCE:CenterFrequency?;")
        )
        response.config.iq_rate = int(float(self._cs_query("SOURCE:IqRate?;")))
        response.config.playback_speed = float(self._cs_query("SOURCE:PlaybackSpeed?;"))
        response.config.bin_count = int(self._cs_query("AOA:BinCount?;"))
        response.config.burst_stride = int(self._cs_query("SOURCE:BurstStride?;"))
        for gain_index in range(4):
            response.config.channel_gain.append(
                int(float(self._cs_query(f"SOURCE:ChannelGain? {gain_index};")))
            )
        response.config.source_path = self._cs_query_multiple("SOURCE:Path?;")
        # except ValueError:
        #    response.error.description = "Invalid config on query"

    def _telemetry(self, response: proto.Response) -> None:
        """Query system telemetry"""

        pass

    def _info(self, response: proto.Response) -> None:
        """Query system info"""

        pass

    def _position(self, response: proto.Response, position: int | None) -> None:
        """Set or query source position"""

        # Generate and execute appropriate CoreService command
        if position is not None:
            cs_command = self._CS_COMMANDS[proto.POSITION].format(
                mode="!", value=position
            )
        else:
            cs_command = self._CS_COMMANDS[proto.POSITION].format(mode="?", value="")
        cs_response = self._cs_execute(cs_command)

        # Check for response validity
        if cs_response is not None:
            error_code = int(cs_response[0])
            if error_code == 0:
                if cs_response[1].isdigit():
                    response.position = int(cs_response[1])
            # TODO: Check response for error messages
        else:
            response.error.description = "CoreService not responding"

    def _cs_control(
        self, response: proto.Response, instruction: proto.Instruction
    ) -> None:
        """Send control commands (no parameters) to CoreService"""

        # Obtain appropriate CoreService command
        cs_command = self._CS_COMMANDS[instruction]
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
        else:
            response.success = False
            response.error.description = "CoreService not responding"
