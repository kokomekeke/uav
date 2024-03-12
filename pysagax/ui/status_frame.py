import tkinter
import tkinter.font
from typing import Any, Callable, Optional

from pysagax.source.source_manager import SourceManager


class StatusFrame(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        source_manager: SourceManager,
        map_server_start_callable: Optional[Callable[[], None]] = None,
        map_server_stop_callable: Optional[Callable[[], None]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        tkinter.Frame.__init__(self, master, *args, **kwargs)
        self.source_manager = source_manager

        self.status_command_string = tkinter.StringVar(value="Not connected")
        self.status_stream_string = tkinter.StringVar(value="Not connected")
        self.status_compass_string = tkinter.StringVar(value="Not connected")
        self.status_map_server_string = tkinter.StringVar(value="Down")
        self.status_path_string = tkinter.StringVar(value="No Source")

        status_command_label_label = tkinter.Label(
            self,
            text="Command:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_command_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_command_label = tkinter.Label(
            self,
            textvariable=self.status_command_string,
            font=tkinter.font.Font(size=10),
        )
        self.status_command_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_stream_label_label = tkinter.Label(
            self,
            text="Stream:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_stream_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_stream_label = tkinter.Label(
            self,
            textvariable=self.status_stream_string,
            font=tkinter.font.Font(size=10),
        )
        self.status_stream_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_compass_label_label = tkinter.Label(
            self,
            text="GPS/Compass:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_compass_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_compass_label = tkinter.Label(
            self,
            textvariable=self.status_compass_string,
            font=tkinter.font.Font(size=10),
        )
        self.status_compass_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_source_label_label = tkinter.Label(
            self,
            text="Source:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_source_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")
        self.status_path_label = tkinter.Label(
            self, textvariable=self.status_path_string
        )
        self.status_path_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        status_map_server_label_label = tkinter.Label(
            self,
            text="Map server:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_map_server_label_label.pack(
            side=tkinter.LEFT, padx=5, pady=10, anchor="w"
        )

        self.status_map_server_label = tkinter.Label(
            self,
            textvariable=self.status_map_server_string,
            font=tkinter.font.Font(size=10),
        )
        self.status_map_server_label.pack(
            side=tkinter.LEFT, padx=5, pady=10, anchor="w"
        )
        if (
            map_server_start_callable is not None
            and map_server_stop_callable is not None
        ):
            self.map_server_button = tkinter.Button(
                self,
                text="DFGS",
                command=self.map_server_button_commands,
            )
            self.map_server_button.pack(side=tkinter.RIGHT)
            self.map_server_start_callable = map_server_start_callable
            self.map_server_stop_callable = map_server_stop_callable

    def map_server_button_commands(self) -> None:
        if self.map_server_button.config("relief")[-1] == "sunken":
            self.map_server_button.config(relief="raised")
            self.map_server_stop_callable()
        else:
            self.map_server_button.config(relief="sunken")
            self.map_server_start_callable()

    def path_update(self):
        self.status_path_string.set(
            self.source_manager.get_current_source_path_str()
            + f" [{self.source_manager.source_status.name}]"
        )
