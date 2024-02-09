from queue import Queue

#TODO: Fix imports with proper package structure
import sys, os
# sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import message.command_pb2 as proto
from loop import Loop

class Interpreter(Loop):
    """Main coordinator process for the sensor software stack"""

    # CoreService commands matching protobuf Instructions
    _CS_COMMANDS = {
        proto.PING: "Core:Ping! {value}",
        proto.POSITION: "Source:Position{mode} {value}",
        proto.SOURCE_START: "Source:Start!",
        proto.SOURCE_STOP: "Source:Stop!",
        proto.REC_START: "Recording:Start!",
        proto.REC_STOP: "Recording:Stop!"
    }

    def __init__(
            self,
            comm_queue_in: Queue,
            comm_queue_out: Queue,
            cs_queue_in: Queue,
            cs_queue_out: Queue,
            *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        self._comm_queue_in = comm_queue_in
        self._comm_queue_out = comm_queue_out
        self._cs_queue_in = cs_queue_in
        self._cs_queue_out = cs_queue_out

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
        self._logger.debug(f"Instruction: {proto.Instruction.Name(command.instruction)}")

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

            case proto.SOURCE_START \
                    | proto.SOURCE_STOP \
                    | proto.REC_START \
                    | proto.REC_STOP:
                self._cs_control(response, command.instruction)
            
            case _:
                response.error.description = "Unknown command"

        # Send response to Communicator
        return response.SerializeToString()
    
    def _cs_execute(self, commands: str | list) -> [str]:
        """Send a list of commands to CoreService, return the result."""

        if not isinstance(commands, list):
            commands = [commands]
        
        # Send commands to CSController
        for command in commands:
            self._cs_queue_out.put(command)
        
        # Wait for responses to the commands
        responses = []
        while len(responses) < len(commands):
            response = self._cs_queue_in.get()

            if response is None:
                break

            responses.append(response)
        
        # Check whether all expected responses arrived
        if len(responses) == len(commands):
            return responses
        
        return None

    def _ping(self, response: proto.Response, ping_data: str) -> None:
        """Send a Ping command to CoreService"""

        # Generate and execute appropriate CoreService command
        cs_command = self._CS_COMMANDS[proto.PING].format(value=ping_data)
        cs_response = self._cs_execute(cs_command)

        # Check for response validity
        if cs_response is not None:
            response.ping_data = cs_response[0]
        else:
            response.error.description = "CoreService not responding"
    
    def _config(self, response: proto.Response, config: proto.Config | None) -> None:
        """Set of query system configuration"""

        pass

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
            cs_command = self._CS_COMMANDS[proto.POSITION].format(mode="!", value=position)
        else:
            cs_command = self._CS_COMMANDS[proto.POSITION].format(mode="?", value="")
        cs_response = self._cs_execute(cs_command)

        # Check for response validity
        if cs_response is not None:
            response.position = int(cs_response[0])
            #TODO: Check response for error messages
        else:
            response.error.description = "CoreService not responding"
    
    def _cs_control(self, response: proto.Response, instruction: proto.Instruction) -> None:
        """Send control commands (no parameters) to CoreService"""

        # Obtain appropriate CoreService command
        cs_command = self._CS_COMMANDS[instruction]
        cs_response = self._cs_execute(cs_command)

        # Check for response validity
        if cs_response is not None:
            #TODO: Check cs_response for success
            response.success = True
        else:
            response.success = False
            response.error.description = "CoreService not responding"
