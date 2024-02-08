import click
from concurrent.futures import ThreadPoolExecutor, wait
from rich.logging import RichHandler
from coloredlogs import install
from logging import getLogger, StreamHandler
from queue import Queue

from communicator import Communicator
from interpreter import Interpreter
from controller import CSController


class Commander:
    """Main process of the service. Holds and controls necessary concurrent tasks"""

    def __init__(self, level: str = "INFO") -> None:
        self._logger = getLogger("Commander")

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

    def start(self) -> None:
        """Start all background processes"""

        self._logger.debug("Starting Commander")

        self._communicator_future = self._pool.submit(self._communicator)
        self._interpreter_futue = self._pool.submit(self._interpreter)
        self._controller_future = self._pool.submit(self._controller)

        # Periodically checking errors in threads
        while True:
            done, running = wait(
                (
                    self._communicator_future,
                    self._interpreter_futue,
                    self._controller_future
                ),
                timeout=1
            )

            for future in done:
                if future.exception(0) is not None:
                    # Trace is lost this way, TODO: fix it
                    raise future.exception()


@click.command()
@click.option("--level", "-l", help="Logging level")
def main(level: str = "INFO") -> None:
    """Root command of CLI"""

    # Validate logging level format
    if level is None:
        level = "INFO"
    if isinstance(level, str):
        level = level.upper()

    # Configure logging format
    setup_logging(level=level)

    #TODO: Implement config file

    commander = Commander(level=level)
    commander.start()

    #while True:
    #    pass


def setup_logging(
        level: str = "INFO",
        show_process_name: bool = False,
        stream_handler: StreamHandler = None
) -> None:
    """Configure logging parameters"""
    
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

