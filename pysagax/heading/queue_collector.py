from __future__ import annotations

import multiprocessing
from typing import Any, Optional, Type
import pyquaternion
import math
import numpy as np
import queue

class QueueValueCollector:
    def __init__(self, mp_values: multiprocessing.Queue[tuple[str, Any]]) -> None:
        self.mp_values: multiprocessing.Queue[tuple[str, Any]] = mp_values
        self.gps: Optional[tuple[float, float]] = None
        self.quaternion: Optional[pyquaternion.Quaternion] = None

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
        except queue.Empty:
            pass

