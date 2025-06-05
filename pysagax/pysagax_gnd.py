#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 09.02.2024.
#
from __future__ import annotations

import multiprocessing
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, wait
from logging import Handler, StreamHandler, getLogger, DEBUG
from pysagax.util.add_logging_level import addLoggingLevel
from os import getpid
from signal import SIGINT, SIGTERM, signal
from typing import Any, Optional

import click
from pysagax.util.load_click_options_from_file import load_click_options_from_file
from coloredlogs import install
from flask import Flask, current_app
from rich.logging import RichHandler

from pysagax.field.scanengine import ScanEngine
from pysagax.gnd.cievents import CIEvents
from pysagax.gnd.commaggregate import CommAggregate
from pysagax.gnd.measurementprocessor import MeasurementProcessor
from pysagax.gnd.commandengine import CommandEngine
from pysagax.gnd.database import ComIntDatabase
from pysagax.gnd.monitoring import Monitoring
from pysagax.gnd.ppgeoloc import PPGeoLoc

try:
    from pysagax.pysagax_gnd_api import run_api
    print("LINUX")
except ImportError:
    from pysagax_gnd_api import run_api
    print('WINDOWS')

from pysagax import __version__


class Commander:
    """Main process of the service. Holds and controls necessary concurrent tasks"""

    def __init__(
        self,
        db_commit_frequency: float,
        level: str,
        db_url: str,
        initialize_db: bool,
    ) -> None:

        self._logger = getLogger("Commander")
        self._manager = multiprocessing.Manager()
        self._pool = ProcessPoolExecutor(max_workers=15)
        multiprocessing.current_process().name = "Commander"

        self._db = ComIntDatabase(db_url)
        # self._example_q = self._manager.Queue(maxsize=1)
        # self._example_proxy = self._manager.dict()
        if initialize_db:
            self._db.initialize_db(self._db.get_app_instance())
            return
        self._telemetry_for_monitoring_q = self._manager.Queue(maxsize=8)
        self._measurement_to_stream_queue = self._manager.Queue(maxsize=64)
        self._api_to_command_engine_commands_q = self._manager.Queue(maxsize=8)
        self._command_engine_to_api_responses_q = self._manager.Queue(maxsize=8)
        self._uavs_to_measurement_processor_q = self._manager.Queue(maxsize=100)
        self._cievents = CIEvents(level=level)
        self._commaggregate = CommAggregate(level=level, db=self._db)
        self._measurement_processor = MeasurementProcessor(
            level=level, db=self._db, db_commit_frequency=db_commit_frequency, measurement_to_stream_queue=self._measurement_to_stream_queue,
        )
        # self._commandengine = CommandEngine(level=level)
        self._monitoring = Monitoring(level=level)
        self._ppgeoloc = PPGeoLoc(level=level, db=self._db)

    def start(self) -> None:
        """Start all background processes"""

        self._logger.debug("Starting Commander")

        api_future = self._pool.submit(
            run_api,
            self._api_to_command_engine_commands_q,
            self._command_engine_to_api_responses_q,
            self._measurement_to_stream_queue,
        )

        cievents_future = self._pool.submit(self._cievents)
        commaggregate_future = self._pool.submit(
            self._commaggregate,
            self._api_to_command_engine_commands_q,
            self._command_engine_to_api_responses_q,
            self._uavs_to_measurement_processor_q,
        )
        measurement_processor_future = self._pool.submit(
            self._measurement_processor,
            self._uavs_to_measurement_processor_q,
            self._telemetry_for_monitoring_q,
        )
        # commandengine_future = self._pool.submit(self._commandengine)
        monitoring_future = self._pool.submit(
            self._monitoring, self._telemetry_for_monitoring_q
        )
        ppgeoloc_future = self._pool.submit(self._ppgeoloc)
        # Periodically checking errors in threads

        signal(SIGINT, self._signal_handler)
        signal(SIGTERM, self._signal_handler)
        while True:
            done, running = wait(
                (
                    api_future,
                    cievents_future,
                    commaggregate_future,
                    measurement_processor_future,
                    # commandengine_future,
                    monitoring_future,
                    ppgeoloc_future,
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


@click.command()
@click.version_option(version=__version__, prog_name="PysagaxGND")
@click.option(
    "--config",
    "-c",
    default="/var/sagax/pysagaxgnd/pysagaxgnd.toml",
    type=click.Path(),
    callback=load_click_options_from_file,
    is_eager=True,
    expose_value=False,
    show_default=True,
    help="Location of the config file. Options set from command line overwrite the ones found in the config file.",
)
@click.option(
    "--db-commit-frequency",
    default=0.1,
    show_default=True,
    help="Frequency (in seconds) of MeasurementProcessor's DB commits. Increase on low-spec hw.",
)
@click.option("--level", "-l", default="INFO", show_default=True, help="Logging level")
@click.option(
    "--db-url",
    help="Database URL",
    default="postgresql+psycopg2://pysagax_gnd:S3cret@localhost/comint",
    show_default=True,
)
@click.option("--initialize-db", is_flag=True)
def main(
    db_commit_frequency: float,
    level: str,
    db_url: str,
    initialize_db: bool,
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
    db_url = "postgresql+psycopg2://pysagax_gnd:S3cret@localhost/comint"
    commander = Commander(db_commit_frequency, level, db_url, initialize_db)
    if initialize_db:
        return
    commander.start()


def setup_logging(
    level: str = "INFO",
    show_process_name: bool = False,
    stream_handler: Optional[Handler] = None,
) -> None:
    """Configure logging parameters"""

    addLoggingLevel("TRACE", DEBUG - 5)

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
