#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 09.02.2024.
#
from __future__ import annotations

import multiprocessing
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, wait
from logging import Handler, StreamHandler, getLogger
from os import getpid
from signal import SIGINT, SIGTERM, signal
from typing import Any, Optional

import click
from coloredlogs import install
from rich.logging import RichHandler

from pysagax.field.communicator import Communicator
from pysagax.field.cscontroller import CSController
from pysagax.field.csparser import CSParser
from pysagax.field.csstreamer import CSStreamer
from pysagax.field.heading import Heading
from pysagax.field.interpreter import Interpreter
from pysagax.field.postproc import PostProc
from pysagax.field.streamer import Streamer
from pysagax.field.telemetry import Telemetry


class Commander:
    """Main process of the service. Holds and controls necessary concurrent tasks"""

    def __init__(self, level: str = "INFO", disk_path: str = "/") -> None:

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
        self._telemetry_in_q = self._manager.Queue()

        self._telemetry_cs_commands_q = self._manager.Queue()
        self._telemetry_cs_responses_q = self._manager.Queue()
        self._heading_commands_q = self._manager.Queue()
        self._heading_data_q = self._manager.Queue()
        self._heading_status_q = self._manager.Queue()

        self._latest_telemetry_proxy = self._manager.dict()
        self._latest_config_id_value = self._manager.Value("i", 0)

        self._communicator = Communicator(level=level)
        self._streamer = Streamer(level=level)

        self._interpreter = Interpreter(
            level=level,
        )
        self._cs_controller = CSController(level=level)

        self._post_proc = PostProc(level=level)
        self._cs_parser = CSParser(level=level)
        self._cs_streamer = CSStreamer(level=level)

        self._telemetry = Telemetry(level=level, data_partition_path=disk_path)
        self._heading = Heading(level=level)

    def start(self) -> None:
        """Start all background processes"""

        self._logger.debug("Starting Commander")

        communicator_future = self._pool.submit(
            self._communicator, self._responses_q, self._commands_q
        )
        interpreter_future = self._pool.submit(
            self._interpreter,
            self._commands_q,
            self._responses_q,
            self._cs_responses_q,
            self._cs_commands_q,
            self._stream_conf_q,
            self._heading_commands_q,
            self._post_proc_commands_q,
            self._post_proc_responses_q,
            self._latest_telemetry_proxy,
            self._latest_config_id_value,
        )
        cs_controller_future = self._pool.submit(
            self._cs_controller,
            self._cs_commands_q,
            self._cs_responses_q,
            self._telemetry_cs_commands_q,
            self._telemetry_cs_responses_q,
        )
        streamer_future = self._pool.submit(
            self._streamer, self._stream_packets_q, self._stream_conf_q
        )
        post_proc_future = self._pool.submit(
            self._post_proc,
            self._stream_packets_q,
            self._post_proc_input_q,
            self._post_proc_commands_q,
            self._post_proc_responses_q,
            self._heading_data_q,
            self._latest_config_id_value,
        )
        cs_parser_future = self._pool.submit(
            self._cs_parser, self._raw_cs_stream_q, self._post_proc_input_q
        )
        cs_streamer_future = self._pool.submit(self._cs_streamer, self._raw_cs_stream_q)
        telemetry_future = self._pool.submit(
            self._telemetry,
            self._stream_packets_q,
            self._telemetry_cs_commands_q,
            self._telemetry_cs_responses_q,
            self._heading_status_q,
            self._latest_telemetry_proxy,
        )
        heading_future = self._pool.submit(
            self._heading,
            self._heading_commands_q,
            self._heading_data_q,
            self._heading_status_q,
        )
        # Periodically checking errors in threads

        signal(SIGINT, self._signal_handler)
        signal(SIGTERM, self._signal_handler)
        while True:
            done, running = wait(
                (
                    communicator_future,
                    interpreter_future,
                    cs_controller_future,
                    streamer_future,
                    post_proc_future,
                    cs_parser_future,
                    cs_streamer_future,
                    heading_future,
                ),
                timeout=1,
            )
            for future in done:
                if future.exception(0) is not None:
                    # Trace is lost this way, TODO: fix it
                    self._logger.critical("Got exception")
                    traceback.print_exception(future.exception(0))
                    self._quit()

    def _signal_handler(self, signal, frame) -> None:
        """Handle incoming signals"""
        self._logger.info(f"Main received signal {signal} (Pid {getpid()}), exiting...")
        self._quit()

    def _quit(self) -> None:
        self._logger.critical("Terminating all processes")
        self._pool.shutdown()
        self._manager.shutdown()
        self._logger.critical("All processes terminated")
        sys.exit(0)


@click.command()
@click.option("--level", "-l", help="Logging level")
@click.option(
    "--disk-path",
    default="/",
    help="Path of the disk which is to be displayed in telemetry",
)
def main(level: str = "INFO", disk_path: str = "/") -> None:
    """Root command of CLI"""

    # Validate logging level format
    if level is None:
        level = "INFO"
    if isinstance(level, str):
        level = level.upper()

    # Configure logging format
    setup_logging(level=level)

    # TODO: Implement config file
    commander = Commander(level=level, disk_path=disk_path)
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
