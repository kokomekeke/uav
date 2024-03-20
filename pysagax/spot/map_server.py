from __future__ import annotations

import math
import multiprocessing
import queue
import threading
import time
import traceback
from typing import Any

from pysagax.spot.calculate_df_corrected import calculate_df_corrected
from pysagax.ui.sgx_dfg_map_server import DFGMapServer
import pysagax.message.data_pb2 as proto_data
from pysagax.util.mat import yaw_pitch_roll_from_quaternion


class MapServer(DFGMapServer):
    def __init__(
        self,
        cs_packet_queue: multiprocessing.Queue[Any] | queue.Queue[Any],
        status_queue: multiprocessing.Queue[str] | queue.Queue[str],
    ) -> None:
        super().__init__()
        self.cs_packet_queue = cs_packet_queue
        self.status_queue = status_queue
        threading.Thread(target=self.cs_packet_handler, daemon=True).start()

    def cs_packet_handler(self) -> None:
        while self.run_thread:
            self._read_queue()
        self.status_queue.put(f"#infoDown")

    def _read_queue(self) -> None:
        data = None
        try:
            while True:
                data = self.cs_packet_queue.get_nowait()
        except queue.Empty:
            pass
        except Exception as e:
            print("[MapServer thread]", e)
            traceback.print_tb(e.__traceback__)
            return
        if isinstance(data, proto_data.Measurement):
            self._handle_packet(packet=data)
        time.sleep(1)  # send updates to clients every 1 second
        self.status_queue.put(
            f"#infoUp on port {self.port}, "
            f"{self.count_clients()} clients, "
            f"{self.total_packets} packets"
        )

    def _handle_packet(self, packet: proto_data.Measurement) -> None:
        # TODO: handle packets with multiple detections
        if len(packet.detection) == 0:
            return
        if len(packet.heading_data.quaternion) != 4:
            return
        yaw, _, _ = yaw_pitch_roll_from_quaternion(packet.heading_data.quaternion)

        df_corrected = calculate_df_corrected(
            df_value=packet.detection[0].azimuth, compass_heading=yaw
        )
        # df_corrected = df_value_mean
        if self.predefined_coords is not None:
            lat, lon = self.predefined_coords
        else:
            lat = packet.heading_data.gps_lat
            lon = packet.heading_data.gps_lon

        isvalid = lambda nums: all(
            [not math.isnan(x) if x is not None else False for x in nums]
        )
        if not isvalid([df_corrected, lat, lon]):
            return  # only update the map server if all values are valid

        self.update_timestamp()
        assert df_corrected is not None
        self.update_angle(df_corrected, packet.detection[0].frequency)
        self.update_lat_lon(lat, lon)
        self.update_clients()
