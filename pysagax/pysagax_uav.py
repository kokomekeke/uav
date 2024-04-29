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

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import os

from pysagax.field.communicator import Communicator
from pysagax.field.cscommand import CSCommand
from pysagax.field.csstreamer import CSStreamer
from pysagax.field.heading import Heading
from pysagax.field.interpreter import Interpreter
from pysagax.field.ppheadingsync import PPHeadingSync
from pysagax.field.ppdetection import PPDetection
from pysagax.field.ppevents import PPEvents
from pysagax.field.ppstreamprep import PPStreamPreparation
from pysagax.field.streamer import Streamer
from pysagax.field.telemetry import Telemetry
from pysagax import __version__


class Commander:
    """Main process of the service. Holds and controls necessary concurrent tasks"""

    def __init__(
        self,
        level: str = "INFO",
        disk_path: str = "/",
        command_port: int = 5555,
        cs_host: str = "127.0.0.1",
        cs_command_port: int = 12936,
        cs_stream_port: int = 12937,
        heading_host: str = "127.0.0.1",
        heading_control_port: int = 5566,
        heading_stream_port: int = 5567,
    ) -> None:

        self._logger = getLogger("Commander")
        self._manager = multiprocessing.Manager()
        self._pool = ProcessPoolExecutor(max_workers=12)

        self._commands_q = self._manager.Queue(maxsize=1)
        self._responses_q = self._manager.Queue(maxsize=1)
        self._stream_packets_q = self._manager.Queue(maxsize=1)
        self._cs_commands_q = self._manager.Queue()
        self._cs_responses_q = self._manager.Queue()
        self._stream_conf_q = self._manager.Queue()
        self._post_proc_commands_q = self._manager.Queue()
        self._post_proc_responses_q = self._manager.Queue()
        self._pp_heading_sync_input_q = self._manager.Queue()
        self._pp_detection_input_q = self._manager.Queue()
        self._pp_events_input_q = self._manager.Queue()
        self._pp_streamprep_input_q = self._manager.Queue()
        self._raw_cs_stream_q = self._manager.Queue()
        self._telemetry_in_q = self._manager.Queue()

        self._telemetry_cs_commands_q = self._manager.Queue()
        self._telemetry_cs_responses_q = self._manager.Queue()
        self._heading_commands_q = self._manager.Queue()
        self._heading_data_q = self._manager.Queue()
        self._heading_status_q = self._manager.Queue()

        self._latest_telemetry_proxy = self._manager.dict()
        self._latest_config_id_value = self._manager.Value("i", 0)

        self._communicator = Communicator(level=level, port=command_port)
        self._streamer = Streamer(level=level)

        self._interpreter = Interpreter(
            level=level,
        )
        self._cs_command = CSCommand(level=level, address=cs_host, port=cs_command_port)

        self._pp_heading_sync = PPHeadingSync(level=level)
        self._pp_detection = PPDetection(level=level)
        self._pp_events = PPEvents(level=level)
        self._pp_streamprep = PPStreamPreparation(level=level)
        self._cs_streamer = CSStreamer(
            level=level, address=cs_host, port=cs_stream_port
        )

        self._telemetry = Telemetry(level=level, data_partition_path=disk_path)
        self._heading = Heading(
            level=level,
            address=heading_host,
            port_control=heading_control_port,
            port_stream=heading_stream_port,
        )

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
        cs_command_future = self._pool.submit(
            self._cs_command,
            self._cs_commands_q,
            self._cs_responses_q,
        )
        streamer_future = self._pool.submit(
            self._streamer, self._stream_packets_q, self._stream_conf_q
        )
        pp_heading_sync_future = self._pool.submit(
            self._pp_heading_sync,
            self._pp_heading_sync_input_q,
            self._pp_detection_input_q,
            self._heading_data_q,
            self._latest_config_id_value,
        )
        pp_detection_future = self._pool.submit(
            self._pp_detection,
            self._pp_detection_input_q,
            self._pp_events_input_q,
            self._post_proc_commands_q,
            self._post_proc_responses_q,
        )
        pp_events_future = self._pool.submit(
            self._pp_events,
            self._pp_events_input_q,
            self._pp_streamprep_input_q,
        )
        pp_streamprep_future = self._pool.submit(
            self._pp_streamprep, self._pp_streamprep_input_q, self._stream_packets_q
        )
        cs_streamer_future = self._pool.submit(
            self._cs_streamer, self._pp_heading_sync_input_q, self._telemetry_in_q
        )
        telemetry_future = self._pool.submit(
            self._telemetry,
            self._stream_packets_q,
            self._telemetry_in_q,
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
                    cs_command_future,
                    streamer_future,
                    pp_heading_sync_future,
                    pp_detection_future,
                    pp_events_future,
                    pp_streamprep_future,
                    cs_streamer_future,
                    telemetry_future,
                    heading_future,
                ),
                timeout=1,
            )
            if self._pool._max_workers < len(running):
                self._logger.critical(
                    f"The number of workers ({len(running)}) exceeds the maximum "
                    f"set for ProcessPoolExecutor ({self._pool._max_workers})"
                )
                self._quit()
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


def set_default_config(ctx, param, conf_path):
    """
    Overwrites the default values for click options from the given config file.
    These values can be further overwritten by providing a config file.
    """
    if os.path.exists(conf_path):
        with open(conf_path, "rb") as f:
            conf = tomllib.load(f)
        ctx.default_map = conf
    else:
        # Can we use the logger instead of print?
        print(f"Config file wasn't found at '{conf_path}'")
    return conf_path


@click.command()
@click.version_option(version=__version__, prog_name="PysagaxUAV")
@click.option(
    "--config",
    "-c",
    default="/var/sagax/pysagaxuav/pysagaxuav.toml",
    type=click.Path(),
    callback=set_default_config,
    is_eager=True,
    expose_value=False,
    show_default=True,
    help="Location of the config file. Options set from command line overwrite the ones found in the config file.",
)
@click.option("--level", "-l", default="INFO", show_default=True, help="Logging level")
@click.option(
    "--command-port",
    "-p",
    type=int,
    default=5555,
    show_default=True,
    help="PysagaxUAV listens on this (ZMQ REP) port for incomming commands",
)
@click.option(
    "--cs-host",
    help="Hostname of CoreService",
    default="127.0.0.1",
    show_default=True,
)
@click.option(
    "--cs-command-port",
    help="CoreService command (ZMQ REP) port",
    default=6000,
    show_default=True,
)
@click.option(
    "--cs-stream-port",
    help="CoreService stream (ZMQ PUB) port",
    default=6001,
    show_default=True,
)
@click.option(
    "--heading-host",
    help="Hostname of Heading module (PySAGAX-Heading)",
    default="127.0.0.1",
    show_default=True,
)
@click.option(
    "--heading-control-port",
    help="Heading control (ZMQ REP) port",
    default=5566,
    show_default=True,
)
@click.option(
    "--heading-stream-port",
    help="Heading stream (ZMQ PUB) port",
    default=5567,
    show_default=True,
)
@click.option(
    "--disk-path",
    default="/",
    show_default=True,
    help="Path of the disk which is to be displayed in telemetry",
)
def main(
    level: str,
    disk_path: str,
    command_port: int,
    cs_host: str,
    cs_command_port: int,
    cs_stream_port: int,
    heading_host: str,
    heading_control_port: int,
    heading_stream_port: int,
) -> None:
    """Root command of CLI"""

    # Validate logging level format
    if level is None:
        level = "INFO"
    if isinstance(level, str):
        level = level.upper()

    # Configure logging format
    setup_logging(level=level)

    # TODO: Implement config file
    commander = Commander(
        level,
        disk_path,
        command_port,
        cs_host,
        cs_command_port,
        cs_stream_port,
        heading_host,
        heading_control_port,
        heading_stream_port,
    )
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
