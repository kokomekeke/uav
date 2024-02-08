import click

from concurrent.futures import ThreadPoolExecutor
from rich.logging import RichHandler
from coloredlogs import install
from logging import basicConfig, getLogger, StreamHandler, root
from signal import signal, SIGINT, SIGTERM
from queue import Queue
from os import kill, getpid

import command_pb2 as proto

from rep import REP

class Loop:
    """Base class for infinitely looping background tasks"""

    def __init__(self, level: str = "INFO") -> None:
        self._logger = getLogger(self.__class__.__name__)
        self._logger.setLevel(level.upper())

        # Set up terminating signals
        signal(SIGINT, self._signal_handler)
        signal(SIGTERM, self._signal_handler)

    def __call__(self) -> None:
        """Execute the main logic of the loop"""

        self._logger.debug("Setting up loop")
        self._pre_loop()

        self._logger.debug("Running main loop")
        while True:
            self._loop()
    
    def _pre_loop(self):
        """Called before main loop starts. Used for initialization"""

        # Override this function
        pass
    
    def _loop(self):
        """The main logic of the loop. This method is called inside a while loop"""

        # Override this function
        pass

    def _signal_handler(self, signal, frame):
        """Handle incoming signals"""

        self._logger.info("Received signal {signal}, exiting...")
        self._quit()
    
    def _quit(self):
        """Stop execution of loop logic"""

        # Kill loop forcefully
        kill(getpid(), 9)


class Communicator(Loop):
    """Background process receiving commands and pushing then to internal queue"""

    def __init__(self, queue_in: Queue, queue_out: Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up command channel
        self._server = REP()
        self._queue_in = queue_in
        self._queue_out = queue_out
    
    def _pre_loop(self):
        # Connect and bind communication ports
        self._server.connect()

    def _loop(self):
        # Hang until a new command is received
        command = self._server.recv()
        self._logger.debug("Command received")

        # Send command to Interpreter
        self._queue_out.put(command)

        # Wait for response from Interpreter
        self._logger.debug("==========")
        response = self._queue_in.get()

        # Send response to remote client
        self._server.resp(response)
        self._logger.debug("Response sent")


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
    ):
        super().__init__(*args, **kwargs)

        self._comm_queue_in = comm_queue_in
        self._comm_queue_out = comm_queue_out
        self._cs_queue_in = cs_queue_in
        self._cs_queue_out = cs_queue_out

    def _loop(self):
        # Hang until a new command is received
        command = self._comm_queue_in.get()

        # Execute command
        response = self._process(command)

        # Send response to Communicator
        self._comm_queue_out.put(response)
    
    def _process(self, raw_command):
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

    def _ping(self, response, ping_data: str) -> None:
        """Send a Ping command to CoreService"""

        # Generate and execute appropriate CoreService command
        cs_command = self._CS_COMMANDS[proto.PING].format(value=ping_data)
        cs_response = self._cs_execute(cs_command)

        # Check for response validity
        if cs_response is not None:
            response.ping_data = cs_response[0]
        else:
            response.error.description = "CoreService not responding"
    
    def _config(self, response, config: proto.Config | None) -> None:
        """Set of query system configuration"""

        pass

    def _telemetry(self, response) -> None:
        """Query system telemetry"""

        pass

    def _info(self, response) -> None:
        """Query system info"""

        pass
    
    def _position(self, response, position: int | None) -> None:
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
    
    def _cs_control(self, response, instruction: proto.Instruction) -> None:
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


class CSController(Loop):
    """Background process communicating with CoreService command interface"""

    def __init__(
            self,
            queue_in: Queue,
            queue_out: Queue,
            #TODO: Define useful defaults
            address: str = "127.0.0.1",
            port: int = 4242,
            *args, **kwargs
    ):
        super().__init__(*args, **kwargs)

        self._queue_in = queue_in
        self._queue_out = queue_out

        #TODO: Set up control channel to CoreService here
    
    def _pre_loop(self):
        pass

        #TODO: Connect to CoreService here
    
    def _loop(self):
        # Hang until a new command is received
        command = self._queue_in.get()

        #TODO: Send command to CoreService and collect response
        self._logger.debug(command)
        response = "132"

        # Send response to Interpreter
        self._queue_out.put(response)


class Commander:
    """Main process of the service. Holds and controls necessary concurrent tasks"""

    def __init__(self, level: str = "INFO"):
        self._logger = getLogger("Commander")
        self._logger.setLevel(level.upper())

        self._pool = ThreadPoolExecutor()

        self._commands = Queue(maxsize=1)
        self._responses = Queue(maxsize=1)
        self._cs_commands = Queue()
        self._cs_responses = Queue()

        self._communicator = Communicator(
            queue_in=self._responses,
            queue_out=self._commands,
            level=level
        )
        self._interpreter = Interpreter(
            comm_queue_in=self._commands,
            comm_queue_out=self._responses,
            cs_queue_in=self._cs_responses,
            cs_queue_out=self._cs_commands,
            level=level
        )
        self._controller = CSController(
            queue_in=self._cs_commands,
            queue_out=self._cs_responses,
            level=level
        )

    def start(self):
        """Start all background processes"""

        self._logger.debug("Starting Commander")

        self._communicator_future = self._pool.submit(self._communicator)
        self._interpreter_futue = self._pool.submit(self._interpreter)
        self._controller_future = self._pool.submit(self._controller)


@click.command()
@click.option("--level", "-l", help="Logging level")
def main(level: str = "INFO"):
    """Root command of CLI"""

    # Set logging display level
    setup_logging(level=level)

    #TODO: Implement config file

    commander = Commander(level=level.upper())
    commander.start()

    while True:
        pass


def setup_logging(
        level: str = None,
        show_process_name: bool = False,
        stream_handler: StreamHandler = None
):
    # Validate logging level format
    if level is None:
        level = "INFO"
    if isinstance(level, str):
        level = level.upper()
    
    if stream_handler is None:
        stream_handler = RichHandler(rich_tracebacks=True)
    
    # Configure logging format
    format = "{asctime} {levelname:<5s} {name:<12s} {message}"
    if show_process_name:
        format = "[{processName}] "+format
    install(level=level, fmt=format, style="{")

    #TODO: Implement log files


if __name__ == "__main__":
    main()

