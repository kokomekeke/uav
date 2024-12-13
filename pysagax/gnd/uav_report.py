import datetime
import re
import time
from typing import Callable, Optional
import pysagax
import pysagax.message.data_pb2 as proto_data
import pysagax.message.command_pb2 as proto_cmd


class UAVReport:
    def __init__(self, uav_id: int, uav_label: str, uav_address: str) -> None:
        self.uav_id = uav_id
        self.uav_label = uav_label
        self.uav_address = uav_address
        self.telemetry = proto_data.Telemetry()
        self.sysinfo = proto_cmd.SystemInfo()
        self.telemetry_timestamp = datetime.datetime.fromtimestamp(0.0)

    def update_from_telemetry(self, telemetry_data: proto_data.Telemetry) -> None:
        self.telemetry.CopyFrom(telemetry_data)
        self.telemetry_timestamp = datetime.datetime.now()

    def update_from_sysinfo(self, sysinfo_data: proto_cmd.SystemInfo) -> None:
        self.sysinfo.CopyFrom(sysinfo_data)

    def evaluate(self, check: Callable[[bool, int, str], None]):
        """
        check(condition, check id, warn message)
        condition is true when the check fails
        check id is for a type of check, so it will trigger the message once only
        """
        re_semver = re.compile(
            r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        )
        timediff_secs = (
            self.telemetry.time.ToDatetime() - self.telemetry_timestamp
        ).total_seconds()
        check(
            abs(timediff_secs) > 2,
            1,
            f"uav system clock is {'behind' if timediff_secs < 0 else 'ahead'} by {abs(timediff_secs)} seconds",
        )
        check(
            pysagax.__version__ != self.sysinfo.software.pysagax_version,
            2,
            f"pysagax version mismatch: gnd={pysagax.__version__} uav={self.sysinfo.software.pysagax_version}",
        )
        check(
            not bool(re.match(re_semver, self.sysinfo.software.cs_version)),
            3,
            f'cs version "{self.sysinfo.software.cs_version}" is invalid',
        )
        check(
            bool(re.match(r"0\.[0-1]\.\d+", self.sysinfo.software.cs_version)),
            4,
            f"cs version {self.sysinfo.software.cs_version} is outdated",
        )
        free_space = self.sysinfo.hardware.disk - self.telemetry.hardware.disk_usage
        check(
            free_space < 20000,
            5,
            f"less than 20 GB space ({free_space} MB) on the disk",
        )
        check(
            free_space / self.sysinfo.hardware.disk < 0.5,
            6,
            f"less than 50% space ({free_space} MB) space left on disk",
        )
        # Todo radio firmware version check
