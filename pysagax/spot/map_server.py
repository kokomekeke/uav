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
            self.read_queue()
        self.status_queue.put(f"#infoDown")

    def read_queue(self) -> None:
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
        if data is not None:
            self.handle_packet(data=data)
        time.sleep(1)  # send updates to clients every 1 second
        self.status_queue.put(
            f"#infoUp on port {self.port}, "
            f"{self.count_clients()} clients, "
            f"{self.total_packets} packets"
        )

    def handle_packet(self, data: dict[str, Any]) -> None:
        df_value_mean = data["aggregated_roi_results"]["df_value_mean"]
        if not df_value_mean:
            return
        compass_heading = data["compass_heading"]

        df_corrected = calculate_df_corrected(
            df_value=df_value_mean, compass_heading=compass_heading
        )
        # df_corrected = df_value_mean
        if self.predefined_coords is not None:
            lat, lon = self.predefined_coords
        else:
            lat = data["gps_lat"]
            lon = data["gps_lon"]

        isvalid = lambda nums: all(
            [not math.isnan(x) if x is not None else False for x in nums]
        )
        if not isvalid([df_corrected, lat, lon]):
            return  # only update the map server if all values are valid

        self.update_timestamp()
        assert df_corrected is not None
        self.update_angle(df_corrected, 1e6)  # TODO: add frequency
        self.update_lat_lon(lat, lon)
        self.update_clients()
