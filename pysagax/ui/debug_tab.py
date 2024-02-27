import tkinter
import tkinter.font
from tkinter import ttk
from typing import Any, Callable, Optional
from pysagax.source.source_manager import CoreServiceStatus, SourceStatus, SourceManager

from pysagax.ui.ui_helpers import en_if
import pysagax.message.command_pb2 as proto_cmd



class DebugTab(ttk.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        send_commands_function: Callable[[str], None],
        abort_commands_function: Callable[[], None],
        source_manager: SourceManager,
    ) -> None:
        super().__init__(master)
        self.source_manager: SourceManager = source_manager
        self.send_commands_function = send_commands_function
        self.abort_commands_function = abort_commands_function

        self.ping_pysagax_button = tkinter.Button(self, text="Ping pysagax-UAV", command=self.ping_pysagax_commands)
        self.ping_pysagax_button.pack(side=tkinter.LEFT, anchor="s")

        self.ping_cs_button = tkinter.Button(self, text="ping CoreService", command=self.ping_cs_commands)
        self.ping_cs_button.pack(side=tkinter.LEFT, anchor="s")

        self.cs_restart_button = tkinter.Button(
            self, text="Restart CS", command=self.cs_restart_commands
        )
        self.cs_restart_button.pack(side=tkinter.RIGHT, anchor="s")
        self.pysagax_restart_button = tkinter.Button(
            self, text="Restart PysagaxUAV", command=self.pysagax_restart_commands
        )
        self.pysagax_restart_button.pack(side=tkinter.RIGHT, anchor="s")

    def ping_cs_commands(self) -> None:
        self.abort_commands_function() # is aborting needed? 
        cmd = proto_cmd.Command(instruction=proto_cmd.CS_PING, ping_data="debug")
        self.send_commands_function(cmd)
        
    def ping_pysagax_commands(self) -> None:
        self.abort_commands_function() # is aborting needed? 
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