from enum import Enum
from typing import Optional
import warnings


# RecordingStatus = Enum("RecordingStatus", ["DISABLED", "ENABLED", "RUNNING", "ERROR"])
class RecordingStatus(Enum):
    """
    Enum for recording statuses.
    Each member's value is based on the possible CS responses for RECORDING:Status!
    Each status has two additional properties: the corresponding icon and color that should be used by the GUI
    """

    # STATUS = icon, color, cs_response[is_activated, is_running]
    DISABLED = "🟣", "Aqua", [False, False]
    ENABLED = "🟢", "LimeGreen", [True, False]
    RUNNING = "🟠", "Red", [True, True]
    ERROR = "❓", "Red", [False, True]

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

    NOT_READY = [False, False]
    READY = [True, False]
    STARTED = [True, True]
    ERROR = [False, True]


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

        self.recording_status: RecordingStatus = RecordingStatus.ERROR
        self.source_status: SourceStatus = SourceStatus.ERROR
        self.cs_status: CoreServiceStatus = CoreServiceStatus.DISCONNECTED

        self.default_source_file_path = "/home/sagax/Generator/"

    def command_status_callback(self, working: bool, current_cmd: str) -> None:
        if "?" in current_cmd or not working:
            self.cs_status = CoreServiceStatus.CONNECTED  # ???
        else:
            self.cs_status = CoreServiceStatus.WORKING

    def source_path_handler(self, resp) -> None:
        self.current_source_path = resp
        try:
            self.current_source = Sources(resp[1])
        except:
            raise Exception(
                f"Unknown source type ({self.current_source_path}) is used by CoreService"
            )

    def source_status_handler(self, resp: list[str]) -> None:
        # updates the source status based on the response from CoreService
        ready = bool(int(resp[1]))
        started = bool(int(resp[2]))
        self.source_status = SourceStatus([ready, started])

    def update_recording_paths(self, path_list: list[str]) -> None:
        Sources.SigMF.params = path_list

    def get_current_source_path_str(self) -> Optional[str]:
        if self.current_source_path == None:
            return None
        return " - ".join(
            part.replace("recording.sigmf-collection", "")
            for part in self.current_source_path[1:]
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
    ) -> str:
        if self.current_source is Sources.NOT_SET:
            raise Exception(f"Source is not intilialized for CoreService")

        if self.current_source.is_tunable:
            source_dependent_commands = (
                f"SOURCE:CenterFrequency! {freq:.0f};"
                f"SOURCE:IqRate! {bw:.0f};"
                f"SOURCE:ChannelGain! 0 {gain};"
                f"SOURCE:ChannelGain! 1 {gain};"
                f"SOURCE:ChannelGain! 2 {gain};"
                f"SOURCE:ChannelGain! 3 {gain};"
            )
        if self.current_source in [Sources.SigMF, Sources.Generator]:
            source_dependent_commands = f"SOURCE:Position! 0;"
        return (
            f"CORE:Version?;"
            f"{source_dependent_commands}"
            f"AOA:BinCount! {bin_count};"
            f"SOURCE:BurstStride! {burst_stride};"
            f"SOURCE:Configure!;"
            f"AOA:Configure!;"
            f"ROI:Enable! 1;"
            f"ROI:CenterFrequency! {roi_center:.0f};"
            f"ROI:Span! {roi_span:.0f};"
            f"ROI:Threshold! {roi_threshold};"
            f"ROI:Configure!;"
        )

    def get_set_source_command(self, source_str: str, params: str):
        """
        Contructs a the command for CoreService based on the display name provided by the GUI
        """
        if source_str == Sources.SigMF.display_name:
            if params[-1] != "/":
                params = params + "/"
            cmd = f'SOURCE:Path! SigMF "{params}recording.sigmf-collection";'
        if source_str == Sources.Generator.display_name:
            cmd = f'SOURCE:Path! SigMF "{self.default_source_file_path}recording.sigmf-collection";'
        elif source_str == Sources.Sidekiq.display_name:
            p = 1  # for single radio
            if params == "Dual":
                p = 2
            cmd = f'SOURCE:Path! Sidekiq "{p}";'
        elif source_str == Sources.UHD.display_name:
            cmd = f"SOURCE:Path! UHD;"

        return cmd

    def is_source_set(self) -> bool:
        # only return true if the source is known and supported
        return self.current_source is not Sources.NOT_SET

    def set_source_recording_status(self, resp: list[str]) -> None:
        # updates the recording status based on the response from CoreService
        enabled = bool(int(resp[1]))
        running = bool(int(resp[2]))
        self.recording_status = RecordingStatus([enabled, running])
