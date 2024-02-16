#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 09.02.2024.
#
from __future__ import annotations
import multiprocessing
from typing import Any, Optional
import click
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, wait
from rich.logging import RichHandler
from coloredlogs import install
from logging import Handler, getLogger, StreamHandler

from field.communicator import Communicator
from field.interpreter import Interpreter
from field.cscontroller import CSController
from pysagax.field.csparser import CSParser
from pysagax.field.csstreamer import CSStreamer
from pysagax.field.postproc import PostProc
from pysagax.field.streamer import Streamer


class Commander:
    """Main process of the service. Holds and controls necessary concurrent tasks"""

    def __init__(self, level: str = "INFO") -> None:
        self._logger = getLogger("Commander")
        self._manager = multiprocessing.Manager()
        self._pool = ProcessPoolExecutor(max_workers=10)

        self._commands_q = self._manager.Queue(maxsize=1)
        self._responses_q = self._manager.Queue(maxsize=1)
        self._stream_packets_q = self._manager.Queue(maxsize=1)
        self._cs_commands_q = self._manager.Queue()
        self._cs_responses_q = self._manager.Queue()
        self._stream_conf_q = self._manager.Queue()
        self._post_proc_commands_q = self._manager.Queue()
        self._post_proc_responses_q = self._manager.Queue()
        self._post_proc_input_q = self._manager.Queue()
        self._raw_cs_stream_q = self._manager.Queue()

        self._communicator = Communicator(level=level)
        self._streamer = Streamer(level=level)

        self._interpreter = Interpreter(
            level=level,
        )
        self._controller = CSController(level=level)

        self._post_proc = PostProc(level=level)
        self._cs_parser = CSParser(level=level)
        self._cs_streamer = CSStreamer(level=level)

    def start(self) -> None:
        """Start all background processes"""

        self._logger.debug("Starting Commander")

        self._communicator_future = self._pool.submit(
            self._communicator, self._responses_q, self._commands_q
        )
        self._interpreter_future = self._pool.submit(
            self._interpreter,
            self._commands_q,
            self._responses_q,
            self._cs_responses_q,
            self._cs_commands_q,
            self._stream_conf_q,
        )
        self._controller_future = self._pool.submit(
            self._controller, self._cs_commands_q, self._cs_responses_q
        )
        self._streamer_future = self._pool.submit(
            self._streamer, self._stream_packets_q, self._stream_conf_q
        )
        self._post_proc_future = self._pool.submit(
            self._post_proc,
            self._stream_packets_q,
            self._post_proc_input_q,
            self._post_proc_commands_q,
            self._post_proc_responses_q,
        )
        self._cs_parser_future = self._pool.submit(
            self._cs_parser, self._raw_cs_stream_q, self._post_proc_input_q
        )
        self._cs_streamer_future = self._pool.submit(
            self._cs_streamer, self._raw_cs_stream_q
        )
        # Periodically checking errors in threads
        while True:
            done, running = wait(
                (
                    self._communicator_future,
                    self._interpreter_future,
                    self._controller_future,
                    self._streamer_future,
                    self._post_proc_future,
                    self._cs_parser_future,
                    self._cs_streamer_future,
                ),
                timeout=1,
            )

            for future in done:
                if future.exception(0) is not None:
                    # Trace is lost this way, TODO: fix it
                    traceback.print_exception(future.exception(0))
                    raise Exception()


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

    # TODO: Implement config file

    commander = Commander(level=level)
    commander.start()

    # while True:
    #    pass


def setup_logging(
    level: str = "INFO",
    show_process_name: bool = False,
    stream_handler: Optional[Handler] = None,
) -> None:
    """Configure logging parameters"""

    if stream_handler is None:
        stream_handler = RichHandler(rich_tracebacks=True)

    # Configure logging format
    format = "{asctime} {levelname:<5s} {name:<12s} {message}"
    if show_process_name:
        format = "[{processName}] " + format
    install(level=level, fmt=format, style="{")

    # TODO: Implement log files


if __name__ == "__main__":
    main()
