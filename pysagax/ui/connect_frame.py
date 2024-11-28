import tkinter
import tkinter.font
from tkinter import PhotoImage, ttk
from typing import Any, Callable, Optional

import numpy as np

from pysagax.util.read_from_conf import read_from_conf
from pysagax.ui.custom_widgets import EntryWithLabel


class ConnectFrame(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        conf: Optional[dict[str, Any]],
        connect_commands_function: Callable[[str], None],
        disconnect_commands_function: Callable[[], None],
        logo_image: Optional[PhotoImage] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        tkinter.Frame.__init__(self, master, *args, **kwargs)



        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)
        self.columnconfigure(3, weight=1)

        self.host_entry= EntryWithLabel(self, "Host:", 0, 0, default_value=read_from_conf(conf, ["defaults", "host"], ""))

        self.icon_frame = tkinter.Frame(self, width=32, height=32)
        self.icon_frame.place(anchor="center", relx=0.5, rely=0.5)
        self.icon_frame.grid(row=0, column=4)
        if logo_image is not None:
            self.icon_label = tkinter.Label(self.icon_frame, image=logo_image)
            self.icon_label.pack()

        self.disconnect_button = tkinter.Button(
            self, text="Disconnect", command=disconnect_commands_function
        )
        self.disconnect_button.grid(column=3, row=0)
        self.disconnect_button.configure(state="disabled")

        self.connect_commands_function = connect_commands_function
        self.connect_button = tkinter.Button(
            self, text="Connect", command=self.connect_commands
        )
        self.connect_button.grid(column=2, row=0)

        self.host_command_port_entry= EntryWithLabel(self, "Host command port:", 1, 1, 5556, tkinter.IntVar)
        self.client_stream_port_entry= EntryWithLabel(self, "Client stream port:", 1, 2, 4242, tkinter.IntVar)

    def connect_commands(self) -> None:
        self.connect_commands_function(self.host_entry.get(), 
            host_cmd_port= self.host_command_port_entry.get(),
            client_stream_port = self.client_stream_port_entry.get(),)
