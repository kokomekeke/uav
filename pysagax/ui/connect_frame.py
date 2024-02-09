import tkinter
import tkinter.font
from tkinter import PhotoImage, ttk
from typing import Any, Callable, Optional

import numpy as np

from pysagax.util.read_from_conf import read_from_conf


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

        self.host_address = tkinter.StringVar(
            value=read_from_conf(conf, ["defaults", "host"], "")
        )

        host_label = tkinter.Label(self, text="Host:")
        host_label.pack(
            side=tkinter.LEFT, fill=tkinter.NONE, padx=(10, 5), pady=10, expand=False
        )

        self.host_entry = tkinter.Entry(self, textvariable=self.host_address, width=15)
        self.host_entry.pack(side=tkinter.LEFT, padx=5, expand=False)

        self.icon_frame = tkinter.Frame(self, width=32, height=32)
        self.icon_frame.place(anchor="center", relx=0.5, rely=0.5)
        self.icon_frame.pack_propagate(False)
        self.icon_frame.pack(side=tkinter.RIGHT)
        if logo_image is not None:
            self.icon_label = tkinter.Label(self.icon_frame, image=logo_image)
            self.icon_label.pack()

        self.disconnect_button = tkinter.Button(
            self, text="Disconnect", command=disconnect_commands_function
        )
        self.disconnect_button.pack(side=tkinter.RIGHT, padx=5, pady=5)
        self.disconnect_button.configure(state="disabled")

        self.connect_commands_function = connect_commands_function
        self.connect_button = tkinter.Button(
            self, text="Connect", command=self.connect_commands
        )
        self.connect_button.pack(side=tkinter.RIGHT)

    def connect_commands(self) -> None:
        self.connect_commands_function(self.host_address.get())
