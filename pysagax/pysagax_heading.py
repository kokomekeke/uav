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
from google.protobuf import json_format
import google.protobuf.message
from coloredlogs import install
from rich.logging import RichHandler

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
)


class HeadingRunner:
    """Main process of the service. Holds and controls necessary concurrent tasks"""

    def __init__(self, level: str, defaults: dict[str, Any]) -> None:
        self._logger = getLogger("HeadingRunner")
        self._logger.setLevel(level=level)
        self._server_rep = REP(address_client="127.0.0.1", port_server=5566)
        self._server_pub = PUB(address_client="127.0.0.1", port_server=5567)
        self._heading_sources = {
            "AHRS": HeadingAHRS,
            "AHRSFTDI": HeadingAHRSFTDI,
            "Encoder": HeadingEncoder,
            "Static": HeadingStatic,
        }
        self._heading_sources_labels = dict()
        for key, value in self._heading_sources.items():
            self._heading_sources_labels[value] = key
        self._heading_data = proto_heading.HeadingData()
        self._heading_status = proto_heading.HeadingStatus()
        self._current_heading_source_label: str = "Static"
        self._current_config: dict[str, Any] = dict()
        self._current_config_types: dict[str, str] = dict()
        self._server_rep.connect()
        self._server_pub.connect()
        self._last_data_packet_time = time.time()
        self._last_update_time = time.time()
        self._defaults = defaults

    def log_status(self, status: str):
        self._logger.info(status)

    def gps_callback(self, lat: float, lon: float) -> None:
        self._heading_data.gps_lat = lat
        self._heading_data.gps_lon = lon
        self._logger.debug(f"GPS callback lat={lat} lon={lon}")
        self._heading_data.timestamp.GetCurrentTime()
        self._last_update_time = time.time()
        self.push_data()

    def quaternion_callback(self, q0: float, q1: float, q2: float, q3: float) -> None:
        del self._heading_data.quaternion[:]
        for q in [q0, q1, q2, q3]:
            self._heading_data.quaternion.append(q)
        self._logger.debug(f"Quaternion callback [{q0} {q1} {q2} {q3}]")
        self._heading_data.timestamp.GetCurrentTime()
        self._last_update_time = time.time()
        self.push_data()

    def offset_callback(self, offset: float) -> None:
        self._heading_data.offset = offset
        self._logger.debug(f"Offset callback offset={offset}")
        self._heading_data.timestamp.GetCurrentTime()
        self._last_update_time = time.time()
        self.push_data()

    def invalid_callback(self) -> None:
        self._heading_data.gps_lat = 0
        self._heading_data.gps_lon = 0
        del self._heading_data.quaternion[:]
        self._logger.warning("Invalidate callback")
        self._heading_data.timestamp.GetCurrentTime()
        self._last_update_time = time.time()
        self.push_data()

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
        for key in self._heading_sources.keys():
            self._heading_status.available_source_types.append(key)
        self._heading_status.selected_source_type = self._current_heading_source_label
        for conf_key, conf_val in self._current_config.items():
            param = proto_heading.HeadingParameter()
            param.name = conf_key
            param.value = str(conf_val)
            param.type = self._current_config_types[param.name]
            self._heading_status.parameters.append(param)

    def start(self) -> None:
        """Start all background processes"""
        heading_source = HeadingStatic()
        self._logger.debug("Starting Heading")
        heading_source.gps_updated_callback = self.gps_callback
        heading_source.quaternion_updated_callback = self.quaternion_callback
        heading_source.offset_updated_callback = self.offset_callback
        heading_source.data_invalid_callback = self.invalid_callback
        heading_source.status_updates_callback = self.log_status
        self.invalid_callback()

        self._logger.info(f"Configured {heading_source.__class__.__name__}")
        for def_key, def_value in self._defaults.items():
            heading_source.update_parameter(def_key, def_value)
            self._logger.info(f"Set {def_key} = {def_value}")

        for conf_key, (
            conf_type,
            conf_default,
        ) in heading_source.get_parameters().items():
            self._current_config[conf_key] = conf_default
            self._current_config_types[conf_key] = conf_type

        while True:

            while True:
                raw_command = self._server_rep.recv(0)
                if raw_command is None:
                    break
                config = proto_heading.HeadingConfig()
                try:
                    config.ParseFromString(raw_command)
                except google.protobuf.message.DecodeError:
                    self._logger.warning("Malformed Protobuf message on ZMQ Command")
                    return
                if not config.selected_source_type:
                    self.craft_status_packet()
                    self._server_rep.resp(self._heading_status.SerializeToString())
                    continue
                if config.selected_source_type != self._current_heading_source_label:

                    heading_source.close()
                    heading_source: HeadingSource = self._heading_sources[
                        config.selected_source_type
                    ]()
                    self._current_heading_source_label = config.selected_source_type
                    self._current_config_types = dict()
                    self._current_config = dict()
                    for conf_key, (
                        conf_type,
                        conf_default,
                    ) in heading_source.get_parameters().items():
                        self._current_config[conf_key] = conf_default
                        self._current_config_types[conf_key] = conf_type
                    heading_source.gps_updated_callback = self.gps_callback
                    heading_source.quaternion_updated_callback = (
                        self.quaternion_callback
                    )
                    heading_source.data_invalid_callback = self.invalid_callback
                    heading_source.status_updates_callback = self.log_status
                    self.invalid_callback()
                    self._logger.info(f"Configured {heading_source.__class__.__name__}")

                self._current_config = dict()
                for param_key, param_val in config.parameters.items():
                    heading_source.update_parameter(param_key, param_val)
                    self._current_config[param_key] = param_val
                    self._logger.info(f"Set {param_key} = {param_val}")
                self.craft_status_packet()
                self._server_rep.resp(self._heading_status.SerializeToString())

            heading_source.loop()
            if self._last_data_packet_time + 1 < time.time():
                self._logger.warning(
                    f"No updates received for {int(time.time() - self._last_update_time)} seconds (sending last available data)"
                )
                self.push_data()
            else:
                pass
        heading_source.close()


@click.command()
@click.option("--level", "-l", help="Logging level", default="INFO")
@click.option("--lat", help="Static GPS Lat", type=float, default=47.5226)
@click.option("--lon", help="Static GPS Lon", type=float, default=19.0646)
@click.option("--ang", help="Static Angle Degrees", type=float, default=120)
def main(level: str, lat: float, lon: float, ang: float) -> None:
    """Root command of CLI"""

    # Validate logging level format
    if level is None:
        level = "INFO"
    if isinstance(level, str):
        level = level.upper()

    # Configure logging format
    setup_logging(level=level)

    # TODO: Implement config file
    heading_runner = HeadingRunner(
        level=level, defaults={"lat": lat, "lon": lon, "angle": ang}
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
    main()
