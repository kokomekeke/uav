import tkinter
import tkinter.font
from tkinter import ttk
from typing import Any, Callable, Optional

from pysagax.ui.ui_helpers import en_if


class PlaybackTab(ttk.Frame):
    def set_buttons_enabled(self) -> None:
        self.start_button.configure(
            state=en_if(
                self.connected
                and (not self.working)
                and self.source_configured
                and (not self.source_running)
            )
        )
        self.rec_button.configure(
            state=en_if(
                self.connected and (not self.working) and self.source_configured
            )
        )
        self.stop_button.configure(
            state=en_if(self.connected and (not self.working) and self.source_running)
        )
        self.abort_button.configure(state=en_if(self.connected and self.working))

    def __init__(
        self, master: tkinter.Misc, send_commands_function: Callable[[str], None]
    ) -> None:
        super().__init__(master)
        self.position_variable = tkinter.DoubleVar()
        self.status_string = tkinter.StringVar(value="Idle")
        self.rec_status_string = tkinter.StringVar(value="🟣️")

        self.connected: bool = False
        self.working: bool = False
        self.source_configured: bool = False
        self.source_running: bool = False

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
            self, text="🔃", command=self.repeat_commands
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
        self.start_local_recording_function: Optional[Callable[[], None]] = None
        self.stop_local_recording_function: Optional[Callable[[], None]] = None
        self.set_repeat_function: Optional[Callable[[bool], None]] = None
        self.abort_commands_function: Optional[Callable[[], None]] = None

    def command_status_callback(self, working: bool, current_cmd: str) -> None:
        if "?" in current_cmd:
            self.working = False
        else:
            self.working = working
        self.set_buttons_enabled()
        self.status_string.set(current_cmd)

    def position_commands(self, event: Any) -> None:
        self.send_commands_function(f"SOURCE:Position! {self.position_variable.get()}")

    def start_commands(self) -> None:
        # self.client.command_thread.enqueue_commands("SOURCE:Start!")
        self.send_commands_function("SOURCE:Start!")

    def rec_commands(self) -> None:
        if self.rec_button.config("relief")[-1] == "sunken":
            if self.stop_local_recording_function is not None:
                self.stop_local_recording_function()
            self.rec_button.config(relief="raised")
        else:
            if self.start_local_recording_function is not None:
                self.start_local_recording_function()
            self.rec_button.config(relief="sunken")

    def stop_commands(self) -> None:
        self.send_commands_function("SOURCE:Stop!")

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
