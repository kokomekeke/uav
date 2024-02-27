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

        self.cs_restart_button = tkinter.Button(
            self, text="Restart CS", command=self.cs_restart_commands
        )
        self.cs_restart_button.pack(side=tkinter.RIGHT, anchor="s")
        self.pysagax_restart_button = tkinter.Button(
            self, text="Restart PysagaxUAV", command=self.pysagax_restart_commands
        )
        self.pysagax_restart_button.pack(side=tkinter.RIGHT, anchor="s")

    def cs_restart_commands(self) -> None:
        self.abort_commands_function()
        cmd = proto_cmd.Command(instruction=proto_cmd.CS_RESTART)
        self.send_commands_function(cmd)

    def pysagax_restart_commands(self) -> None:
        self.abort_commands_function()
        cmd = proto_cmd.Command(instruction=proto_cmd.PY_RESET)
        self.send_commands_function(cmd)