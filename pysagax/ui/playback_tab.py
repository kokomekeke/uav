import tkinter
import tkinter.font
from tkinter import ttk
from typing import Any, Callable, Optional
from pysagax.source.source_manager import (
    CoreServiceStatus,
    SourceStatus,
    SourceManager,
    SourceMode,
)

from pysagax.ui.ui_helpers import en_if
import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data


class PlaybackTab(ttk.Frame):

    def telemetry_string_format(
        self,
        telem: Optional[proto_data.Telemetry],
        sysinfo: Optional[proto_cmd.SystemInfo],
    ) -> str:
        if sysinfo is None:
            sysinfo = proto_cmd.SystemInfo()
            sysinfo.software.cs_version = "?"
            sysinfo.software.pysagax_version = "?"
        if telem is None:
            return f"PySAGAX {sysinfo.software.pysagax_version}, CS {sysinfo.software.cs_version}\nNo telemetry"

        # Generating strings with warnings (0-division safe) using whitespace indentation
        disk_usage_str = (
            f"      {'⚠️' if telem.hardware.disk_usage >= sysinfo.hardware.disk * 0.9 else '   '} Disk: "
            f"{'{:,}'.format(telem.hardware.disk_usage).replace(',', ' ')} MB / "
            f"{'{:,}'.format(sysinfo.hardware.disk).replace(',', ' ')} MB"
        )
        ram_usage_str = (
            f"      {'⚠️' if telem.hardware.ram_usage >= sysinfo.hardware.ram * 0.9 else '   '} RAM usage:"
            f"{'{:,}'.format(telem.hardware.ram_usage).replace(',', ' ')} MB / "
            f"{'{:,}'.format(sysinfo.hardware.ram).replace(',', ' ')} MB"
        )

        cpu_temp_str = (
            f"      {'⚠️' if telem.hardware.cpu_temperature >= 90 else '   '} CPU temp: "
            f"{telem.hardware.cpu_temperature:5.0f}°C"
        )
        radio_temp_str = (
            f"      {'⚠️' if max(telem.hardware.radio_temperature, default=-1) >= 90 else '   '} Radio temp: "
            f"{', '.join([f'{temp:4.0f}°C' for temp in telem.hardware.radio_temperature])}"
        )

        return (
            f"{telem.hardware.hostname}\n{telem.time.ToDatetime()} UTC\n"
            f"PySAGAX {sysinfo.software.pysagax_version}, CS {sysinfo.software.cs_version}\n"
            f"Source module Status: {proto_data.Telemetry.Source.Status.Name(telem.source.status)} \n"
            f"Source module Mode: {proto_data.Telemetry.Source.Mode.Name(telem.source.mode)} \n"
            f"\tPosition:{'{:,}'.format(telem.source.position).replace(',', ' ')} / "
            f"{'{:,}'.format(telem.source.length).replace(',', ' ')} \n"
            f"Recording module {proto_data.Telemetry.Recording.Status.Name(telem.recording.status)} "
            f"{'{:,}'.format(telem.recording.length).replace(',', ' ')}\n"
            f"Heading module {telem.heading.status} [{telem.heading.selected_source_type}]\n"
            f"ScanEngine {telem.scanengine_state}\n"
            f"HW:  CPU usage: {telem.hardware.cpu_usage * 100:4.0f}%"
            f"\n{cpu_temp_str}"
            f"\n{disk_usage_str}"
            f"\n{ram_usage_str}"
            f"\n{radio_temp_str}"
        )

    def config_string_format(self, cp: Optional[proto_cmd.Response]) -> str:
        if cp is None:
            return "CONF unknown"
        heading_conf_str = ", ".join(
            f"\n\t{k}={cp.config.heading.parameters[k]}"
            for k in sorted(cp.config.heading.parameters.keys())
        )
        return (
            f"CONFIG {cp.id}\n"
            f"CS Source {cp.config.cs.source_type}\n\t[{cp.config.cs.source_path}]\n"
            f"IQ = {'{:,}'.format(int(cp.config.cs.iq_rate)).replace(',', ' ')} Hz, "
            f"Center = {'{:,}'.format(int(cp.config.cs.center_frequency)).replace(',', ' ')} Hz\n"
            f"Bin count = {'{:,}'.format(cp.config.cs.bin_count).replace(',', ' ')}, "
            f"Stride = {'{:,}'.format(cp.config.cs.burst_stride).replace(',', ' ')}\n"
            f"Gain = {', '.join([f'{g:4.1f}' for g in cp.config.cs.channel_gain])}\n"
            f"Heading: {cp.config.heading.selected_source_type} [{heading_conf_str}]\n"
            f"ScanEngine: [{str(cp.config.se)}]\n"
            f"Antenna configuration: {cp.config.cs.aoa_antenna_id}/{cp.config.cs.aoa_antenna_count}"
        )

    def update(
        self,
        current_position: Optional[int] = None,
        source_length: Optional[int] = None,
    ):
        if source_length is not None:
            self.position_slider.configure(to=source_length)
        if current_position is not None:
            self.position_variable.set(current_position)
        self.update_buttons()
        self.update_recording_status()
        
        telemetry_str = self.telemetry_string_format(
            self.source_manager.latest_telemetry, self.source_manager.latest_info
        )
        self.telemetry_string.set(telemetry_str)
        
        # change text color to red if warning sign is in the telemetry string
        if "⚠️" in telemetry_str: 
            self.telemetry_label.config(fg="#f00")
        else:
            self.telemetry_label.config(fg="#000")

        self.config_string.set(
            f"{self.config_string_format(self.source_manager.latest_config)}"
        )

    def update_buttons(self) -> None:
        self.start_button.configure(
            state=en_if(
                self.source_manager.cs_status
                in [CoreServiceStatus.CONNECTED, CoreServiceStatus.WORKING]
                and self.source_manager.source_status is SourceStatus.ENABLED
                and self.source_manager.source_mode is SourceMode.MANUAL
            )
        )

        self.rec_button.configure(
            state=en_if(
                self.source_manager.cs_status
                in [CoreServiceStatus.CONNECTED, CoreServiceStatus.WORKING]
                and self.source_manager.source_status
                in [SourceStatus.ENABLED, SourceStatus.RUNNING]
            )
        )
        self.stop_button.configure(
            state=en_if(
                self.source_manager.cs_status
                in [CoreServiceStatus.CONNECTED, CoreServiceStatus.WORKING]
                and self.source_manager.source_status
                in [SourceStatus.RUNNING, SourceStatus.UNKNOWN]
            )
        )

        self.abort_button.configure(
            state=en_if(self.source_manager.cs_status is CoreServiceStatus.WORKING)
        )

    def update_recording_status(self) -> None:
        self.rec_status_string.set(self.source_manager.recording_status.icon)
        self.rec_status_label.configure(fg=self.source_manager.recording_status.color)

    def __init__(
        self,
        master: tkinter.Misc,
        send_commands_function: Callable[[str], None],
        source_manager: SourceManager,
    ) -> None:
        super().__init__(master)
        self.source_manager: SourceManager = source_manager

        self.position_variable = tkinter.DoubleVar()
        self.status_string = tkinter.StringVar(value="Idle")
        self.telemetry_string = tkinter.StringVar(value="Telemetry data")
        self.config_string = tkinter.StringVar(value="Config data")
        self.rec_status_string = tkinter.StringVar(value="🟣️")

        self._pack_playback_controls()
        self._pack_top_frame()

        self.send_commands_function = send_commands_function
        self.start_recording_function: Optional[Callable[[], None]] = None
        self.stop_recording_function: Optional[Callable[[], None]] = None
        self.set_repeat_function: Optional[Callable[[bool], None]] = None
        self.abort_commands_function: Optional[Callable[[], None]] = None

    def _pack_top_frame(self):
        self.top_frame = ttk.Frame(self)
        self.top_frame.pack(side=tkinter.TOP, fill=tkinter.X)
        self.status_label = tkinter.Label(
            self.top_frame,
            textvariable=self.status_string,
            font=tkinter.font.Font(size=8),
            anchor="w",
            justify="left",
            width=20,
            wraplength=200,
        )
        self.status_label.pack(side=tkinter.LEFT, anchor="n")
        self.telemetry_label = tkinter.Label(
            self.top_frame,
            textvariable=self.telemetry_string,
            font=tkinter.font.Font(size=8),
            padx=10,
            anchor="w",
            justify="left",
            wraplength=200,
        )

        self.telemetry_label.pack(side=tkinter.RIGHT, anchor="n")
        self.config_label = tkinter.Label(
            self.top_frame,
            textvariable=self.config_string,
            font=tkinter.font.Font(size=8),
            padx=10,
            anchor="w",
            justify="left",
            wraplength=200,
        )
        self.config_label.pack(side=tkinter.RIGHT, anchor="n")

        # Warping long lines in telemetry and config labels
        status_label_width_px = 144
        get_top_frame_width = (
            lambda: self.top_frame.winfo_width() - self.status_label.winfo_width()
        )  # returns the remaining space that the telemetry and config labels need to share
        self.telemetry_label.bind(
            "<Configure>",
            lambda e: self.telemetry_label.config(
                wraplength=get_top_frame_width() * 0.35
            ),
        )  # event handler for resizing: telemetry gets 35% of the space
        self.config_label.bind(
            "<Configure>",
            lambda e: self.config_label.config(wraplength=get_top_frame_width() * 0.65),
        )  # event handler for resizing: config gets 65% of the space

    def _pack_playback_controls(self):
        self.playback_control_frame = ttk.Frame(self)
        self.playback_control_frame.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        self.position_slider = tkinter.Scale(
            self.playback_control_frame,
            from_=0,
            to=1,
            variable=self.position_variable,
            orient=tkinter.HORIZONTAL,
            command=self.position_commands,
        )
        self.position_slider.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        self.start_button = tkinter.Button(
            self.playback_control_frame, text="▶️", command=self.start_commands
        )
        self.start_button.pack(side=tkinter.LEFT, anchor="s")
        self.rec_button = tkinter.Button(
            self.playback_control_frame, text="●", command=self.rec_commands
        )
        self.rec_button.pack(side=tkinter.LEFT, anchor="s")
        self.rec_status_label = tkinter.Label(
            self.playback_control_frame,
            textvariable=self.rec_status_string,
            font=tkinter.font.Font(size=16),
            fg="#ccc",
        )
        self.rec_status_label.pack(side=tkinter.LEFT, anchor="s", expand=False)
        self.stop_button = tkinter.Button(
            self.playback_control_frame, text="■", command=self.stop_commands
        )
        self.stop_button.pack(side=tkinter.LEFT, anchor="s")
        self.repeat_button = tkinter.Button(
            self.playback_control_frame, text="⟲", command=self.repeat_commands
        )
        self.repeat_button.pack(side=tkinter.LEFT, anchor="s")
        self.abort_button = tkinter.Button(
            self.playback_control_frame, text="abort", command=self.abort_commands
        )
        self.abort_button.pack(side=tkinter.RIGHT, anchor="s")

        self.start_button.configure(state="disabled")
        self.rec_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.abort_button.configure(state="disabled")

    def display_command_status(self, current_cmd) -> None:
        self.update_buttons()
        self.status_string.set(current_cmd)  # .instruction)

    def position_commands(self, event: Any) -> None:
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.POSITION
        cmd.kind = proto_cmd.Command.WRITE
        cmd.position = int(self.position_variable.get())
        self.send_commands_function(cmd)

    def start_commands(self) -> None:
        cmd_source_start = proto_cmd.Command()
        cmd_source_start.instruction = proto_cmd.SOURCE_START
        self.send_commands_function([cmd_source_start])

    def rec_commands(self) -> None:
        if self.rec_button.config("relief")[-1] == "sunken":
            if self.stop_recording_function is not None:
                self.stop_recording_function()
            self.rec_button.config(relief="raised")
        else:
            if self.start_recording_function is not None:
                self.start_recording_function()
            self.rec_button.config(relief="sunken")

    def stop_commands(self) -> None:
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.SOURCE_STOP
        self.send_commands_function(cmd)

    def repeat_commands(self) -> None:
        if self.set_repeat_function is None:
            return
        if self.repeat_button.config("relief")[-1] == "sunken":
            self.set_repeat_function(False)
            self.repeat_button.config(relief="raised")
        else:
            self.set_repeat_function(True)
            self.repeat_button.config(relief="sunken")

    def abort_commands(self) -> None:
        if self.abort_commands_function is not None:
            self.abort_commands_function()
