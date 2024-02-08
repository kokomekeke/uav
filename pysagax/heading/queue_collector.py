from __future__ import annotations

import multiprocessing
from typing import Any, Optional, Type
import pyquaternion
import math
import numpy as np
import queue

from pysagax.util.read_from_conf import read_from_conf

class QueueValueCollector:
    def __init__(self, mp_values: multiprocessing.Queue[tuple[str, Any]], conf) -> None:
        self.mp_values: multiprocessing.Queue[tuple[str, Any]] = mp_values
        self.gps: Optional[tuple[float, float]] = None
        self.quaternion: Optional[pyquaternion.Quaternion] = None
        self.offset = read_from_conf(conf, ["heading", "offset"], 0) / 180 * np.pi

    def heading(self) -> Optional[float]:
        if self.quaternion is None:
            return None
        heading = self.quaternion.rotate(np.array([1.0, 0.0, 0.0]))
        return math.atan2(
            heading[1],
            heading[0],
        )

    def collect_values(self) -> None:
        try:
            while not self.mp_values.empty():
                key, value = self.mp_values.get_nowait()
                print(f"{key} -> {value}")
                if key == "gps":
                    self.gps = value
                elif key == "quaternion":
                    self.quaternion = (
                        pyquaternion.Quaternion(value) if value is not None else None
                    )
                elif key == "offset":
                    self.offset = value
        except queue.Empty:
            pass

