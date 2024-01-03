from __future__ import annotations

import multiprocessing
import multiprocessing.managers
import queue
import re
import threading
import traceback
import typing
from typing import Optional

import numpy as np
import scipy
import serial

import pysagax
from pysagax import (
    BaseConnection,
    CompassSensor,
    CoreServicePacket,
    CoreServiceParser,
    CoreServiceROIResultPacket,
)
from pysagax.heading.queue_collector import QueueValueCollector
from pysagax.util import MultiQueue


class StreamAndCompassProcess(
    CoreServiceParser, BaseConnection, multiprocessing.Process
):
    def __init__(
        self,
        queues: MultiQueue,
        disconnect_value: multiprocessing.managers.ValueProxy[int],
        status_value: queue.Queue[str] | multiprocessing.Queue[str],
    ):
        CoreServiceParser.__init__(self)
        BaseConnection.__init__(self)
        multiprocessing.Process.__init__(self)
        self.queues = queues

        self.packet_count = 0
        """
        Overall packet count
        """

        self.mp_status = status_value
        """
        Status message queue for multiprocessing process
        """

        self.mp_disconnect: multiprocessing.managers.ValueProxy[int] = disconnect_value
        """
        Disconnect signal for multiprocessing process
        """

        self.compass_host_port: Optional[str] = None

        self.encoder_port: Optional[str] = None

        self.compass = None

        self.heading_queue: Optional[QueueValueCollector] = None

        self.compass_offset = 0.0

        self.encoder_offset = 0.0

        self.use_sensor_fusion: bool = False

        self.mean_window_seconds: Optional[
            multiprocessing.managers.ValueProxy[float]
        ] = None  # TODO: set from gui

        self.past_roi_results: dict[str, list[typing.Any]] = {
            "df_values": [],
            "df_elevations": [],
        }

        self.df_aggregated_last_updated_ns = (
            0  # timestamp for the last mean angle calculation
        )

        self.aggregated_roi_results: dict[str, Optional[float]] = {
            "df_value_mean": None,
            "df_value_std": None,
            "df_elevation_mean": None,
            "df_elevation_std": None,
        }

    def receive_on_socket(self, data: bytes) -> None:
        """
        When data is received on the socket, this function will construct a packet object from the binary data.
        """
        for cs_packet in self.extract_packets(data):
            cs_packet.packet_index = self.packet_count
            self.packet_count += 1
            if self.heading_queue is not None:
                self.heading_queue.collect_values()
                compass_angle = self.heading_queue.heading()
                gps_lat, gps_lon = (
                    self.heading_queue.gps
                    if self.heading_queue.gps is not None
                    else None,
                    None,
                )
            else:
                compass_angle = None
                gps_lat = None
                gps_lon = None

            compass_heading = (
                pysagax.normalize_angle(compass_angle - self.compass_offset)
                if compass_angle is not None
                else None
            )

            if isinstance(cs_packet, CoreServiceROIResultPacket):
                try:
                    self.update_aggregated_results(cs_packet)
                except (
                    TypeError
                ) as e:  # TODO: multiprocessing debug (JIRA issue ALTS-150)
                    print("[MultiprocessingError@aggregating]:", e)

                # TODO: if we receive no roi packets for a time then update aggregated results with None

            result: dict[str, typing.Any] = {
                "cs_packet": cs_packet,
                "aggregated_roi_results": self.aggregated_roi_results,
                "compass_angle": compass_angle if self.compass is not None else None,
                "compass_heading": compass_heading,
                "gps_lat": gps_lat,
                "gps_lon": gps_lon,
                "encoder_angle": None,
                "encoder_heading": None,
            }

            self.queues.put(result)

    def run(self) -> None:
        """
        Entry point of the stream collecting process.
        """

        self.run_socket()
        self.mp_status.put("END")

    def is_disconnect(self) -> bool:
        """
        Returns: if the socket should manually disconnect
        """
        assert self.mp_disconnect is not None
        try:
            return bool(self.mp_disconnect.value)
        except TypeError as e:  # TODO: multiprocessing debug (JIRA issue ALTS-150)
            print("[MultiprocessingError]:", e)
            print("trying to read mp_disconnect.value again")
            from time import sleep

            sleep(0.1)
            try:
                return bool(self.mp_disconnect.value)
            except TypeError as e:  # TODO: multiprocessing debug (JIRA issue ALTS-150)
                print("[MultiprocessingError]:", e)
                # traceback.print_exception(type(e), e, e.__traceback__)
                print("Failed to read mp_disconnect.value a second time")
            return True

    def display_status_callback(self, message: str) -> None:
        """
        Display a status message (on the GUI status bar)
        """
        assert self.mp_status
        self.mp_status.put(message)

    def update_aggregated_results(self, cs_packet: CoreServiceROIResultPacket) -> None:
        assert self.mean_window_seconds is not None
        if self.mean_window_seconds.value <= 0:
            # no averaging in this case
            self.aggregated_roi_results["df_value_mean"] = cs_packet.roi_azimuth
            self.aggregated_roi_results["df_value_std"] = 0.0
            self.aggregated_roi_results["df_elevation_mean"] = cs_packet.roi_elevation
            self.aggregated_roi_results["df_elevation_std"] = 0.0
            return

        self.past_roi_results["df_values"].append(cs_packet.roi_azimuth)
        self.past_roi_results["df_elevations"].append(cs_packet.roi_elevation)

        if (
            cs_packet.time_ns - self.df_aggregated_last_updated_ns
            > self.mean_window_seconds.value * 1e9
        ):
            # calculate new mean values
            self.aggregated_roi_results["df_value_mean"] = scipy.stats.circmean(
                self.past_roi_results["df_values"], high=np.pi, low=-np.pi
            )
            self.aggregated_roi_results["df_value_std"] = scipy.stats.circstd(
                self.past_roi_results["df_values"], high=np.pi, low=-np.pi
            )
            self.aggregated_roi_results["df_elevation_mean"] = scipy.stats.circmean(
                self.past_roi_results["df_elevations"], high=np.pi, low=-np.pi
            )
            self.aggregated_roi_results["df_elevation_std"] = scipy.stats.circstd(
                self.past_roi_results["df_elevations"], high=np.pi, low=-np.pi
            )

            self.past_roi_results["df_values"] = []
            self.past_roi_results["df_elevations"] = []

            self.df_aggregated_last_updated_ns = cs_packet.time_ns
