import tkinter
import tkinter.font
from tkinter import ttk
from typing import Any, Callable, Optional
from pysagax.source.source_manager import CoreServiceStatus, SourceStatus, SourceManager
from pysagax.ui.custom_widgets import EntryWithLabel

from pysagax.ui.ui_helpers import en_if
import pysagax.message.command_pb2 as proto_cmd
from pysagax.util.get_ip import get_ip


STREAM_LEVEL = {
    "HEARTBEAT": proto_cmd.StreamTarget.StreamLevel.HEARTBEAT,
    "TELEMETRY": proto_cmd.StreamTarget.StreamLevel.TELEMETRY,
    "DETECTION": proto_cmd.StreamTarget.StreamLevel.DETECTION,
    "SPECTRUM": proto_cmd.StreamTarget.StreamLevel.SPECTRUM,
}  # TODO: list protobuf enum names and values more elegantly


class DebugTab(ttk.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        send_commands_function: Callable[[str], None],
        abort_commands_function: Callable[[], None],
        source_manager: SourceManager,
        client,
    ) -> None:
        super().__init__(master)
        self.source_manager: SourceManager = source_manager
        self.send_commands_function = send_commands_function
        self.abort_commands_function = abort_commands_function
        self.client = client

        self._pack_stream_controls()

        self.buttons_frame = ttk.Frame(self)
        self.ping_pysagax_button = tkinter.Button(
            self.buttons_frame,
            text="Ping pysagax-UAV",
            command=self.ping_pysagax_commands,
        )
        self.ping_pysagax_button.pack(side=tkinter.BOTTOM, anchor="w")

        self.ping_cs_button = tkinter.Button(
            self.buttons_frame, text="ping CoreService", command=self.ping_cs_commands
        )
        self.ping_cs_button.pack(side=tkinter.BOTTOM, anchor="w")

        self.cs_restart_button = tkinter.Button(
            self.buttons_frame, text="Restart CS", command=self.cs_restart_commands
        )
        self.cs_restart_button.pack(side=tkinter.BOTTOM, anchor="w")
        self.pysagax_restart_button = tkinter.Button(
            self.buttons_frame,
            text="Restart PysagaxUAV",
            command=self.pysagax_restart_commands,
        )
        self.pysagax_restart_button.pack(side=tkinter.BOTTOM, anchor="w")
        self.buttons_frame.pack(side=tkinter.LEFT, anchor="ne")
        self.stream_packet_stat_string = tkinter.StringVar(value="stream packet stats")
        self.stream_packet_label = tkinter.Label(
            self,
            textvariable=self.stream_packet_stat_string,
            font=tkinter.font.Font(size=8),
            anchor="w",
            justify="left",
        )
        self.stream_packet_label.pack(side=tkinter.LEFT, anchor="ne")

    def _pack_stream_controls(self):
        self.stream_controls_frame = ttk.Frame(self)
        self.stream_controls_frame.columnconfigure(0, weight=2)
        self.stream_controls_frame.columnconfigure(1, weight=1)

        self.stream_level_str = tkinter.StringVar(value="SPECTRUM")

        self.telemetry_level_combo = ttk.Combobox(
            self.stream_controls_frame, textvariable=self.stream_level_str
        )
        self.telemetry_level_combo["values"] = list(STREAM_LEVEL.keys())
        self.telemetry_level_combo.grid(row=0, column=0, columnspan=1)

        self.stream_target_ip_str = tkinter.StringVar(value="target IP:")
        self.stream_target_ip_label = tkinter.Label(
            self.stream_controls_frame, textvariable=self.stream_target_ip_str
        )
        self.stream_target_ip_label.grid(row=0, column=1)

        self.heartbeat_to_entry = EntryWithLabel(
            self.stream_controls_frame,
            "Heartbeat TO:",
            0,
            1,
            "1",
        )
        self.telemetry_to_entry = EntryWithLabel(
            self.stream_controls_frame,
            "Telemetry TO:",
            0,
            2,
            "1",
        )
        self.config_stream_button = tkinter.Button(
            self.stream_controls_frame,
            text="Configure stream",
            command=self.configure_stream_commands,
        )
        self.config_stream_button.grid(row=3, column=0)
        self.stream_controls_frame.pack(side=tkinter.LEFT, anchor="ne")

    def ping_cs_commands(self) -> None:
        self.abort_commands_function()  # is aborting needed?
        cmd = proto_cmd.Command(instruction=proto_cmd.CS_PING, ping_data="debug")
        self.send_commands_function(cmd)

    def ping_pysagax_commands(self) -> None:
        self.abort_commands_function()  # is aborting needed?
        cmd = proto_cmd.Command(instruction=proto_cmd.PING, ping_data="debug")
        self.send_commands_function(cmd)

    def cs_restart_commands(self) -> None:
        self.abort_commands_function()
        cmd = proto_cmd.Command(instruction=proto_cmd.CS_RESTART)
        self.send_commands_function(cmd)

    def pysagax_restart_commands(self) -> None:
        self.abort_commands_function()
        cmd = proto_cmd.Command(instruction=proto_cmd.PY_RESET)
        self.send_commands_function(cmd)

    def ping_response_handler(self, resp: proto_cmd.Response) -> None:
        print(f"PING response: ", resp.ping_data)

    def cs_ping_response_handler(self, resp: proto_cmd.Response) -> None:
        print(f"CS PING response: ", resp.ping_data)

    def update_stream_packet_stats(self, stats) -> None:
        stat_string = (
            str(stats)
            .replace(": {", ":{\n\t")
            .replace(",", ",\n\t")
            .replace("},\n\t", "},\n")
        )
        self.stream_packet_stat_string.set(stat_string)
        pass

    def configure_stream_commands(self) -> None:
        host_address = self.client.client_window.connect_frame.host_address.get()

        cmd_stream_stop = proto_cmd.Command(instruction=proto_cmd.STREAM_STOP)
        cmd_stream_stop.target.id = 1
        cmd_stream_stop.target.level = STREAM_LEVEL[self.stream_level_str.get()]
        cmd_stream_stop.target.address = get_ip(host_address)
        cmd_stream_stop.target.port = 4242
        cmd_stream_stop.target.heartbeat_timeout = int(self.heartbeat_to_entry.get())
        cmd_stream_stop.target.telemetry_timeout = int(self.telemetry_to_entry.get())

        cmd_stream_start = proto_cmd.Command(instruction=proto_cmd.STREAM_START)
        cmd_stream_start.target.id = 1
        cmd_stream_start.target.level = STREAM_LEVEL[self.stream_level_str.get()]
        cmd_stream_start.target.address = get_ip(host_address)
        cmd_stream_start.target.port = 4242
        cmd_stream_start.target.heartbeat_timeout = int(self.heartbeat_to_entry.get())
        cmd_stream_start.target.telemetry_timeout = int(self.telemetry_to_entry.get())

        self.stream_target_ip_str.set(f"target IP: {cmd_stream_start.target.address}")
        self.send_commands_function([cmd_stream_stop, cmd_stream_start])
