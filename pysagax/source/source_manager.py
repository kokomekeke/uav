from enum import Enum
from typing import Optional
import warnings

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data


class RecordingStatus(Enum):
    """
    Enum for recording statuses.
    Each member's value is based on the possible CS responses for RECORDING:Status!
    Each status has two additional properties: the corresponding icon and color that should be used by the GUI
    """

    # STATUS = icon, color, cs_response[is_activated, is_running]
    DISABLED = "🟣", "Aqua", proto_data.Telemetry.Recording.Status.DISABLED
    ENABLED = "🟢", "LimeGreen", proto_data.Telemetry.Recording.Status.ENABLED
    RUNNING = "🟠", "Red", proto_data.Telemetry.Recording.Status.RUNNING
    UNKNOWN = "❓", "Red", 0

    def __new__(cls, icon, color, cs_response):
        member = object.__new__(cls)
        member._value_ = cs_response  # len(cls._member_names_) + 1
        object.__setattr__(member, "icon", icon)
        object.__setattr__(member, "color", color)
        return member

    def __setattr__(self, name, value):
        # Overwriting __setattr__() to make the properties immutable (is there a better way to it?)
        if name in ("icon", "color"):
            warnings.warn(
                f"Cannot modify property '{name}' of RecordingStatus member {self._name_}"
            )
        else:
            super().__setattr__(name, value)


class SourceStatus(Enum):
    """
    Enum for source statuses.
    Each member's value is based on the possible CS responses for SOURCE:Status!
    """

    DISABLED = proto_data.Telemetry.Source.Status.DISABLED
    ENABLED = proto_data.Telemetry.Source.Status.ENABLED
    RUNNING = proto_data.Telemetry.Source.Status.RUNNING
    UNKNOWN = 0


class CoreServiceStatus(Enum):
    DISCONNECTED = 0
    CONNECTED = 1  # connected and not working
    WORKING = 2


sidekiq_bw_tuple = (
    "541.667k",
    "1.920M",
    "2.4576M",
    "2.8M",
    "3.84M",
    "4M",
    "4.9152M",
    "5.6M",
    "7.68M",
    "9.8304M",
    "10M",
    "11.2M",
    "15.36M",
    "16M",
    "20M",
    "21.6667M",
    "22M",
    "23.04M",
    "30.72M",
    "40M",
    "61.44M",
)


class Sources(Enum):
    """
    Enum for recording statuses.
    Each member's value is based on the possible CS responses for RECORDING:Status!
    Each status has two additional properties: the corresponding icon and color that should be used by the GUI
    """

    # Source = name, display_name, is_tunable, params, default_param_index, bandwith list
    NOT_SET = "NULL", None, False, None, None, None
    UHD = "UHD", "USRP", True, None, None, None
    Sidekiq = "Sidekiq", "Sidekiq", True, ["Single", "Dual"], 0, sidekiq_bw_tuple
    SigMF = (
        "SigMF",
        "Recording",
        False,
        None,
        None,
        None,
    )  # parameter list gets filled at connecting
    Generator = "Generator", "Generator", False, None, None, None

    def __new__(
        cls, name, display_name, is_tunable, params, default_param_index, bandwith_tuple
    ):
        member = object.__new__(cls)
        member._value_ = name  # len(cls._member_names_) + 1
        object.__setattr__(member, "display_name", display_name)
        object.__setattr__(member, "is_tunable", is_tunable)
        object.__setattr__(member, "params", params)
        object.__setattr__(member, "default_param_index", default_param_index)
        object.__setattr__(member, "bandwith_tuple", bandwith_tuple)
        return member

    def __setattr__(self, name, value):
        # Overwriting __setattr__() to make the properties immutable (is there a better way to it?)
        # params can be modified since for recordings it is acquired after connecting
        if name in ("name", "display_name", "is_tunable"):
            warnings.warn(
                f"Cannot modify property '{name}' of Sources member {self._name_}"
            )
        else:
            super().__setattr__(name, value)


class SourceManager:
    def __init__(self) -> None:
        """
        Keeps track of current source properties in the CoreService.
        Most of the source-dependent checks and functions needed in the GUI
        have been moved here.
        """
        self.current_source: Sources = Sources.NOT_SET
        self.current_source_path: Optional[list[str]] = None

        self.recording_status: RecordingStatus = RecordingStatus.UNKNOWN
        self.source_status: SourceStatus = SourceStatus.UNKNOWN
        self.cs_status: CoreServiceStatus = CoreServiceStatus.DISCONNECTED
        self.is_cs_configuring: bool = False 
        self.config_status: dict[int, int] = {"responses": 0, "queue": 0}

        self.latest_telemetry: Optional[proto_data.Telemetry] = None

        self.default_source_file_path = "/home/sagax/Generator/"

    def command_status_callback(self, working: bool, current_cmd: str) -> None:
        if working:
            self.cs_status = CoreServiceStatus.WORKING
        else:
            self.cs_status = CoreServiceStatus.CONNECTED

    def source_config_handler(self, resp) -> None:
        if resp.success: # CONFIG commands are being processed by pysagaxUAV
            self.is_cs_configuring = True
            return
        self.current_source_path = str(resp.config.source_path).strip().split(" ")
        try:
            self.current_source = Sources(self.current_source_path[0])
        except:
            self.current_source = Sources.NOT_SET

    def source_config_status_handler(self, resp) -> None:
        if bool(resp.config_status.finish_time.ToSeconds()):
            self.is_cs_configuring = False
        self.config_status["responses"] = len(resp.config_status.responses)
        self.config_status["queue"] = len(resp.config_status.queue)

    def source_telemetry_handler(self, packet: proto_data.Telemetry) -> None:
        # updates the source status based on the response from CoreService
        self.source_status = SourceStatus(packet.source.status)
        self.recording_status = RecordingStatus(packet.recording.status)
        self.latest_telemetry = packet

    def update_recording_paths(self, path_list: list[str]) -> None:
        Sources.SigMF.params = path_list

    def get_current_source_path_str(self) -> Optional[str]:
        if self.current_source_path == None:
            return None
        return " - ".join(
            part.replace("recording.sigmf-collection", "")
            for part in self.current_source_path
        )

    def get_source_display_names(self) -> list[str]:
        # returns the display names for defined sources
        source_list = [s.display_name for s in Sources if s is not Sources.NOT_SET]
        return source_list

    def get_source_params(
        self, source_str: str
    ) -> tuple[Optional[list[str]], Optional[int]]:
        # returns the list of possible parameters (paths for sigmf, single/double mode for sidekiq)
        # also returns the default parameter's index
        queried_source = [s for s in Sources if s.display_name == source_str][0]
        try:
            return queried_source.params, queried_source.default_param_index
        except:
            return None, None

    def get_config_commands(
        self,
        freq,
        bw,
        gain,
        bin_count,
        burst_stride,
        roi_center,
        roi_span,
        roi_threshold,
    ) -> list[proto_cmd.Command]:
        if self.current_source is Sources.NOT_SET:
            raise Exception(f"Source is not intilialized for CoreService")

        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.CONFIG
        cmd.config.center_frequency = float(freq)
        cmd.config.iq_rate = int(bw)
        # cmd.config.playback_speed = 1
        cmd.config.bin_count = int(bin_count)
        cmd.config.burst_stride = int(burst_stride)
        cmd.config.channel_gain[:] = 4 * [int(gain)]
        cmd.config.roi.append(
            self.get_single_roi_mask(roi_center, roi_span, roi_threshold)
        )
        # TODO: heading?
        # TODO: mean_window
        # TODO: cmd.config.type = LIVE/RECORDED #why is it needed???
        return [cmd]

    def get_single_roi_mask(
        self, center_frequency: float, span: float, threshold: float, roi_id: int = 0
    ):
        roi_mask = proto_cmd.ROIMask()
        roi_mask.center_frequency = float(center_frequency)
        roi_mask.span = float(span)
        roi_mask.threshold = float(threshold)
        roi_mask.roi_id = roi_id
        return roi_mask

    def get_set_source_command(self, source_str: str, params: str):
        """
        Contructs a the command for pysagaxUAV based on the display name provided by the GUI
        """
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.CONFIG
        print("SOURCE_STRING:", source_str)
        if source_str == Sources.SigMF.display_name:
            if params[-1] != "/":
                params = params + "/"
            source_path = f"SigMF {params}recording.sigmf-collection"
        elif source_str == Sources.Generator.display_name:
            source_path = (
                f"SigMF {self.default_source_file_path}recording.sigmf-collections"
            )
        elif source_str == Sources.Sidekiq.display_name:
            p = 1  # for single radio
            if params == "Dual":
                p = 2
            source_path = f"Sidekiq {p}"
        elif source_str == Sources.UHD.display_name:
            source_path = f"UHD"
        cmd.config.source_path = source_path

        return cmd

    def is_source_set(self) -> bool:
        # only return true if the source is known and supported
        return self.current_source is not Sources.NOT_SET
