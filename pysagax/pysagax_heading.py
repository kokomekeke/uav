#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 13.03.2024.
#
from __future__ import annotations
import logging

import time
from logging import Handler, getLogger
from typing import Any, Optional
import typing


import click
from pysagax.util.load_click_options_from_file import load_click_options_from_file
from google.protobuf import json_format
import google.protobuf.message
from coloredlogs import install
from rich.logging import RichHandler

from pysagax import __version__
import pysagax.message.heading_pb2 as proto_heading
from pysagax.communication.pub_sub import PUB
from pysagax.communication.req_rep_tcp import REP
from pysagax.heading.heading_sources import (
    HeadingAHRS,
    HeadingAHRSFTDI,
    HeadingAHRSUSB,
    HeadingEncoder,
    HeadingSource,
    HeadingStatic,
    HeadingFlightInfo,
    HeadingMavlink,
)

HEADING_SOURCES = {
    "AHRS": HeadingAHRS,
    "AHRSFTDI": HeadingAHRSFTDI,
    "AHRSUSB": HeadingAHRSUSB,
    "Encoder": HeadingEncoder,
    "Static": HeadingStatic,
    "FlightInfo": HeadingFlightInfo,
    "Mavlink (WIP)": HeadingMavlink,
}


class HeadingRunner:
    """Main process of the service. Holds and controls necessary concurrent tasks"""

    def __init__(
        self,
        level: str,
        control_address: str,
        stream_address: str,
        defaults: dict[str, Any],
    ) -> None:
        self._logger = getLogger("HeadingRunner")
        self._logger.setLevel(level=level)

        rep_address, rep_port = control_address.split(":")
        pub_address, pub_port = stream_address.split(":")
        self._server_rep = REP(address_client=rep_address, port_server=rep_port)
        self._server_pub = PUB(address_client=pub_address, port_server=pub_port)

        self._heading_source: Optional[HeadingSource] = None

        self._heading_data = proto_heading.HeadingData()
        self._heading_status = proto_heading.HeadingStatus()
        self._current_heading_source_label: str = "Static"
        self._server_rep.connect()
        self._server_pub.connect()
        self._last_data_packet_time = time.time()
        self._last_update_time = time.time()
        self._defaults = defaults

    def log_status(self, status: str):
        self._logger.info(status)

    def _update_packet_timestamp(self, timestamp: Optional[float]) -> None:
        """
        If provided, set timestamp as packet.timestamp, else set it as current time.
        timestamp: UNIX timestamp in seconds.
        """
        if timestamp is not None:
            self._heading_data.timestamp.seconds = int(timestamp)
            self._heading_data.timestamp.nanos = int(timestamp % 1 * 1e9)
        else:
            self._heading_data.timestamp.GetCurrentTime()

    def gps_callback(
        self, lat: float, lon: float, timestamp: Optional[float] = None
    ) -> None:
        """timestamp: use if provided by heading source. UNIX timestamp in seconds."""
        self._heading_data.gps_lat = lat
        self._heading_data.gps_lon = lon
        self._logger.debug(f"GPS callback lat={lat} lon={lon}")
        self._update_packet_timestamp(timestamp)
        self._last_update_time = time.time()
        self.push_data()

    def quaternion_callback(
        self,
        q0: float,
        q1: float,
        q2: float,
        q3: float,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        q0, q1, q2, q3: quaternion in scalar first form: [w, x, y, z]
        timestamp: use if provided by heading source. UNIX timestamp in seconds.
        """
        del self._heading_data.quaternion[:]
        for q in [q0, q1, q2, q3]:
            self._heading_data.quaternion.append(q)
        self._logger.debug(f"Quaternion callback [{q0} {q1} {q2} {q3}]")
        self._update_packet_timestamp(timestamp)
        self._last_update_time = time.time()
        self.push_data()

    def altitude_callback(
        self, altitude: float, timestamp: Optional[float] = None
    ) -> None:
        """timestamp: use if provided by heading source. UNIX timestamp in seconds."""
        self._heading_data.altitude = altitude
        self._logger.debug(f"Altitude callback ({altitude}")
        self._update_packet_timestamp(timestamp)
        self._last_update_time = time.time()
        self.push_data()

    def offset_callback(self, offset: float) -> None:
        self._heading_data.offset = offset
        self._logger.debug(f"Offset callback offset={offset}")
        self._heading_data.timestamp.GetCurrentTime()
        self._last_update_time = time.time()
        self.push_data()

    def invalid_callback(
        self, msg: str = "", clear_values: Optional[bool] = True
    ) -> None:
        if clear_values:
            self._heading_data.gps_lat = 0
            self._heading_data.gps_lon = 0
            self._heading_data.altitude = 0
            del self._heading_data.quaternion[:]
            self._heading_data.timestamp.GetCurrentTime()
            self._last_update_time = time.time()
            self.push_data()
        self._logger.warning(f"Invalidate callback: {msg}")

    def _protobuf_to_log(
        self, protobuf: typing.Any, format_str: str = "{}", level: int = logging.INFO
    ) -> None:
        message_str = (
            json_format.MessageToJson(protobuf, indent=0)
            .replace("\n", "")
            .replace("\r", "")
        )
        self._logger.log(level, format_str.format(message_str))

    def push_data(self) -> None:
        self._server_pub.publ(self._heading_data.SerializeToString())
        self._protobuf_to_log(self._heading_data)
        self._last_data_packet_time = time.time()

    def craft_status_packet(self) -> None:
        self._heading_status = proto_heading.HeadingStatus()
        for key in HEADING_SOURCES.keys():
            self._heading_status.available_source_types.append(key)
        self._heading_status.selected_source_type = self._current_heading_source_label
        for conf_key, (
            conf_type,
            conf_val,
        ) in self._heading_source.get_parameters().items():
            param = proto_heading.HeadingParameter()
            param.name = conf_key
            param.value = str(conf_val)
            param.type = conf_type
            self._heading_status.parameters.append(param)

    def _create_heading_source(
        self, config: Optional[proto_heading.HeadingConfig] = None
    ):
        if config is None:
            # Use static heading by default
            self._heading_source = HeadingStatic()
            self._current_heading_source_label = "Static"
            for def_key, def_value in self._defaults.items():
                self._heading_source.update_parameter(def_key, def_value)
                self._logger.info(f"Set {def_key} = {def_value}")
        else:
            self._heading_source: HeadingSource = HEADING_SOURCES[
                config.selected_source_type
            ]()
            self._current_heading_source_label = config.selected_source_type
        self._heading_source.gps_updated_callback = self.gps_callback
        self._heading_source.quaternion_updated_callback = self.quaternion_callback
        self._heading_source.altitude_updated_callback = self.altitude_callback
        self._heading_source.offset_updated_callback = self.offset_callback
        self._heading_source.data_invalid_callback = self.invalid_callback
        self._heading_source.status_updates_callback = self.log_status
        self.invalid_callback()
        self._logger.info(f"Configured {self._heading_source.__class__.__name__}")

    def start(self) -> None:
        """Start all background processes"""
        self._create_heading_source()
        self._logger.debug("Starting Heading")
        while True:
            self._execute_config_command()
            self._heading_source.loop()
            if self._last_data_packet_time + 1 < time.time():
                self._logger.warning(
                    f"No updates received for {int(time.time() - self._last_update_time)} seconds (sending last available data)"
                )
                self.push_data()
            else:
                pass
        self._heading_source.close()

    def _execute_config_command(self):
        while True:
            raw_command = self._server_rep.recv(0)
            if raw_command is None:
                break
            config = proto_heading.HeadingConfig()
            config.ParseFromString(raw_command)
            if not config.selected_source_type:
                self.craft_status_packet()
                self._server_rep.resp(self._heading_status.SerializeToString())
                continue

            if config.selected_source_type != self._current_heading_source_label:
                self._heading_source.close()
                self._create_heading_source(config)

            for param_key, param_val in config.parameters.items():
                if self._heading_source.update_parameter(param_key, param_val):
                    self._logger.info(f"Set {param_key} = {param_val}")
                else:
                    self._logger.error(
                        f'Invalid parameter "{param_key}" for heading source type "{type(self._heading_source)}"'
                    )
            self._heading_source.initialize()
            self.craft_status_packet()
            self._server_rep.resp(self._heading_status.SerializeToString())


def generate_help_epilog():
    """Generates a nice help text of the available heading sources and their parameters"""

    import terminaltables
    from textwrap import wrap

    table_data = [
        ["Source", "parameter", "type", "default", "source description"],
    ]
    for src_name, src_cls in HEADING_SOURCES.items():
        src_obj = src_cls()

        key_cell = []
        type_cell = []
        value_cell = []
        for conf_key, (conf_type, conf_val) in src_obj.get_parameters().items():
            key_cell.append(str(conf_key))
            type_cell.append(str(conf_type))
            value_cell.append(str(conf_val))

        table_data.append(
            [
                src_name,
                "\n".join(key_cell),
                "\n".join(type_cell),
                "\n".join(value_cell),
                "\n".join(wrap(src_obj.help_description, 50)),
            ]
        )
    table = terminaltables.DoubleTable(table_data, "Supported Heading Sources")
    table.inner_row_border = True

    return "\n\b\n" + str(table.table)


@click.command(epilog=generate_help_epilog())
@click.version_option(version=__version__, prog_name="PysagaxHeading")
@click.option(
    "--config",
    "-c",
    default="/var/sagax/pysagaxuav/pysagaxheading.toml",
    type=click.Path(),
    callback=load_click_options_from_file,
    is_eager=True,
    expose_value=False,
    show_default=True,
    help="Location of the config file. Options set from command line overwrite the ones found in the config file.",
)
@click.option("--level", "-l", help="Logging level", default="INFO")
@click.option(
    "--control-address",
    "-c",
    help="IP and port of control channel from pysagaxUAV",
    default="127.0.0.1:5566",
    show_default=True,
)
@click.option(
    "--stream-address",
    "-s",
    help="IP and port of stream channel to pysagaxUAV",
    default="127.0.0.1:5567",
    show_default=True,
)
@click.option("--lat", help="Static GPS Lat", type=float, default=47.5226)
@click.option("--lon", help="Static GPS Lon", type=float, default=19.0646)
@click.option("--ang", help="Static Angle Degrees", type=float, default=120)
@click.option(
    "--alt", help="Static Altitude (above ground, meters)", type=float, default=0
)
@click.option(
    "--source",
    "-S",
    help="Heading source to initialize at startup.",
    default="Static",
    show_default=True,
)
@click.option(
    "--defaults",
    "-d",
    type=(str, str),
    multiple=True,
    help="\n\b\nParameters for initializing a heading source at startup. Given as key-value pairs.\n Usage: pysagax-heading -S Static -d lat 47.5226 -d lon 19.0646 -d angle 120\n ",
    default=[["lat", 47.5226], ["lon", 19.0646], ["angle", 120]],
    show_default=True,
)
def main(
    level: str,
    control_address: str,
    stream_address: str,
    lat: float,
    lon: float,
    ang: float,
    alt: float,
    source: str,
    defaults: dict,
) -> None:
    """
    PysagaxHEADING is a sevice handling a variety of heading sources and forwarding their data to pysagaxUAV.
    The heading data contains current location (lattitude, longitude, altitude) and current attitude (eg. yaw, pitch, roll)
    """
    defaults = dict(defaults)

    # Validate logging level format
    if level is None:
        level = "INFO"
    if isinstance(level, str):
        level = level.upper()

    # Configure logging format
    setup_logging(level=level)

    # TODO: Implement config file
    heading_runner = HeadingRunner(
        level=level,
        control_address=control_address,
        stream_address=stream_address,
        defaults={"lat": lat, "lon": lon, "angle": ang, "alt": alt},
    )
    heading_runner.start()


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


if __name__ == "__main__":
    main(max_content_width=200)  # max_content_width sets the help text's wrapping
