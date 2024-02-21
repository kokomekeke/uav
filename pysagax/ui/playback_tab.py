import tkinter
import tkinter.font
from tkinter import ttk
from typing import Any, Callable, Optional
from pysagax.source.source_manager import CoreServiceStatus, SourceStatus, SourceManager

from pysagax.ui.ui_helpers import en_if
import pysagax.message.command_pb2 as proto


class PlaybackTab(ttk.Frame):
    def update_buttons(self) -> None:
        self.start_button.configure(
            state=en_if(
                self.source_manager.cs_status
                in [CoreServiceStatus.CONNECTED, CoreServiceStatus.WORKING]
                # and self.source_manager.source_status is SourceStatus.READY
                # TODO: when Telemetry response is implented uncomment
            )
        )

        self.rec_button.configure(
            state=en_if(
                self.source_manager.cs_status
                in [CoreServiceStatus.CONNECTED, CoreServiceStatus.WORKING]
                # and self.source_manager.source_status
                # in [SourceStatus.READY, SourceStatus.STARTED]
                # TODO: when Telemetry response is implented uncomment
            )
        )
        self.stop_button.configure(
            state=en_if(
                self.source_manager.cs_status
                in [CoreServiceStatus.CONNECTED, CoreServiceStatus.WORKING]
                and self.source_manager.source_status
                in [SourceStatus.STARTED, SourceStatus.ERROR]
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
        self.rec_status_string = tkinter.StringVar(value="🟣️")

        self.position_slider = tkinter.Scale(
            self,
            from_=0,
            to=1,
            variable=self.position_variable,
            orient=tkinter.HORIZONTAL,
            command=self.position_commands,
        )
        self.position_slider.pack(side=tkinter.TOP, expand=True, fill=tkinter.X)
        self.start_button = tkinter.Button(self, text="▶️", command=self.start_commands)
        self.start_button.pack(side=tkinter.LEFT)
        self.rec_button = tkinter.Button(self, text="⏺️️", command=self.rec_commands)
        self.rec_button.pack(side=tkinter.LEFT)
        self.rec_status_label = tkinter.Label(
            self,
            textvariable=self.rec_status_string,
            font=tkinter.font.Font(size=16),
            fg="#ccc",
        )
        self.rec_status_label.pack(side=tkinter.LEFT, expand=False)
        self.stop_button = tkinter.Button(self, text="⏹️", command=self.stop_commands)
        self.stop_button.pack(side=tkinter.LEFT)
        self.repeat_button = tkinter.Button(
            self, text="⟲", command=self.repeat_commands
        )
        self.repeat_button.pack(side=tkinter.LEFT)
        self.status_label = tkinter.Label(
            self,
            textvariable=self.status_string,
            font=tkinter.font.Font(size=8),
        )
        self.status_label.pack(side=tkinter.LEFT)
        self.abort_button = tkinter.Button(self, text="⛔", command=self.abort_commands)
        self.abort_button.pack(side=tkinter.RIGHT)

        self.start_button.configure(state="disabled")
        self.rec_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.abort_button.configure(state="disabled")

        self.send_commands_function = send_commands_function
        self.start_recording_function: Optional[Callable[[], None]] = None
        self.stop_recording_function: Optional[Callable[[], None]] = None
        self.set_repeat_function: Optional[Callable[[bool], None]] = None
        self.abort_commands_function: Optional[Callable[[], None]] = None

    def display_command_status(self, current_cmd) -> None:
        self.update_buttons()
        self.status_string.set(current_cmd)  # .instruction)

    def position_commands(self, event: Any) -> None:
        cmd = proto.Command()
        cmd.instruction = proto.POSITION
        cmd.position = int(self.position_variable.get())
        self.send_commands_function(cmd)

    def start_commands(self) -> None:
        cmd = proto.Command()
        cmd.instruction = proto.SOURCE_START
        self.send_commands_function(cmd)

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
        cmd = proto.Command()
        cmd.instruction = proto.SOURCE_STOP
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
