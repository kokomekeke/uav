from __future__ import annotations

import multiprocessing
import os
import queue
import re
import threading
import traceback
from datetime import datetime
from typing import Any

import pandas as pd

from pysagax.df.lena_core_service import (
    CoreServiceDebugPacket,
    CoreServiceROIResultPacket,
)
from pysagax.spot.calculate_df_corrected import calculate_df_corrected


class RecordingThread(threading.Thread):
    def __init__(
        self,
        cs_packet_queue: queue.Queue[Any] | multiprocessing.Queue[Any],
        status_queue: queue.Queue[str] | multiprocessing.Queue[str],
    ) -> None:
        super().__init__(daemon=True)
        self.cs_packet_queue = cs_packet_queue
        self.status_queue = status_queue

        self.do_stop = False

        self.latest_peaks = [0, 0, 0, 0]
        self.latest_quality: float = 0.0

        self.buffer: dict[str, list[Any]] = {
            "time_ns": [],
            "df_angle": [],
            "df_corrected": [],
            "compass_angle": [],
            "compass_heading": [],
            "df_elevation": [],
            "quality": [],
            "peak0": [],
            "peak1": [],
            "peak2": [],
            "peak3": [],
            "df_angle_mean": [],
            "df_angle_std": [],
            "df_elevation_mean": [],
            "df_elevation_std": [],
            "lat": [],
            "lon": [],
        }

    def run(self) -> None:
        self.status_queue.put("Recording started")
        start_time_string = datetime.now().strftime("%Y%m%d_%H%M%S")
        while not self.do_stop:
            try:
                data = self.cs_packet_queue.get(timeout=0.2)
                self.handle_packet(data=data)
            except queue.Empty:
                pass
            except Exception as e:
                print("[Recording thread]", e)
                traceback.print_tb(e.__traceback__)
                return
        self.status_queue.put("saving recording...")
        try:
            self.save_recording(start_time_string)
        except Exception as e:
            self.status_queue.put(f"Error while saving recording: {e}")

    def handle_packet(self, data: dict[str, Any]) -> None:
        ##TODO: many similarities with client window packet handler. Maybe export those to a single function?
        packet = data["cs_packet"]
        try:
            time_ns = packet.time_ns
            if isinstance(packet, CoreServiceDebugPacket):
                # save the peaks to later match with the next ROI results
                if packet.title == "peaks":
                    regex = r"peak(\d+)=(\d+)"
                    matches = re.findall(
                        regex, str(packet)
                    )  # creating a list of (ChannelID, PeakValue) tuples from the debug message
                    peaks = [peak[1] for peak in matches]
                    self.latest_peaks = peaks
                elif packet.title == "q":
                    quality = float(packet.contents.decode().strip())
                    self.latest_quality = quality

            if isinstance(packet, CoreServiceROIResultPacket):
                compass_angle = data["compass_angle"]
                compass_heading = data["compass_heading"]

                df_angle = packet.roi_azimuth
                df_elevation = packet.roi_elevation
                df_corrected = calculate_df_corrected(
                    df_value=df_angle, compass_heading=compass_heading
                )

                self.buffer["time_ns"].append(time_ns)
                self.buffer["df_angle"].append(df_angle)
                self.buffer["df_corrected"].append(df_corrected)
                self.buffer["compass_angle"].append(compass_angle)
                self.buffer["compass_heading"].append(compass_heading)
                self.buffer["df_elevation"].append(df_elevation)
                self.buffer["quality"].append(self.latest_quality)
                self.buffer["peak0"].append(self.latest_peaks[0])
                self.buffer["peak1"].append(self.latest_peaks[1])
                self.buffer["peak2"].append(self.latest_peaks[2])
                self.buffer["peak3"].append(self.latest_peaks[3])
                self.buffer["df_angle_mean"].append(
                    data["aggregated_roi_results"]["df_value_mean"]
                )
                self.buffer["df_angle_std"].append(
                    data["aggregated_roi_results"]["df_value_std"]
                )
                self.buffer["df_elevation_mean"].append(
                    data["aggregated_roi_results"]["df_elevation_mean"]
                )
                self.buffer["df_elevation_std"].append(
                    data["aggregated_roi_results"]["df_elevation_std"]
                )
                self.buffer["lat"].append(data["gps_lat"])
                self.buffer["lon"].append(data["gps_lon"])

        except Exception as e:
            print("[Recording packet handler]", e)
            traceback.print_tb(e.__traceback__)

    def save_recording(self, start_time_string: str) -> None:
        dataframe = pd.DataFrame(data=self.buffer)

        os.makedirs("spotclient_recordings", exist_ok=True)
        filepath = f"spotclient_recordings/{start_time_string}.csv"
        dataframe.to_csv(filepath)
        self.status_queue.put(f"{len(dataframe.index)} lines saved at {filepath}")

        ##TODO: plot results of recording
        """ df_value_recording_deg = [d * 180 / np.pi if d is not None else None for d in self.buffer["df_angle"]]
        df_corrected_recording_deg = [d * 180 / np.pi if d is not None else None for d in self.buffer["df_corrected"]]
        compass_heading_recording_deg = [d * 180 / np.pi if d is not None else None for d in self.buffer["compass_heading"]]
        encoder_heading_recording_deg = [d * 180 / np.pi if d is not None else None for d in self.buffer["encoder_heading"]]
        fig, (ax1, ax2) = pyplot.subplots(1, 2)
        ax1.plot(compass_heading_recording_deg, df_value_recording_deg, color="red", label="compass-DF")
        ax1.plot(encoder_heading_recording_deg, df_value_recording_deg, color="green", label="encoder-DF")
        ax1.legend()
        
        ax2.plot(df_value_recording_deg, color="blue", label="DF angle")
        ax2.plot(df_corrected_recording_deg, color="cyan", label="DF corrected")
        ax2.plot(compass_heading_recording_deg, color="red", label="compass")
        ax2.plot(encoder_heading_recording_deg, color="green", label="encoder")
        ax2.legend()
        
        ax1.grid(visible=True)
        ax1.set_ylabel("DF angle")
        ax1.set_xlabel("Compass and encoder angle")
        ax2.grid(visible=True)
        ax2.set_ylabel("Angle")
        ax2.set_xlabel("Sample")
        ax1.set_xlim(-180, 180)
        ax1.set_ylim(-180, 180)
        ax2.set_ylim(-180, 180)
        pyplot.show(block=False) """
