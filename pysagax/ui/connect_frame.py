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
        send_commands_function: Callable[[str], None],
        connect_commands_function: Callable[[str], None],
        disconnect_commands_function: Callable[[], None],
        logo_image: Optional[PhotoImage] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.send_commands = send_commands_function
        compass_offset = -1  ##TODO: should be an argument of master.client?
        encoder_offset = np.pi  ##TODO: should be an argument of master.client?

        self.host_address = tkinter.StringVar(
            value=read_from_conf(conf, ["defaults", "host"], "")
        )
        self.encoder_port_string = tkinter.StringVar(
            value=read_from_conf(conf, ["defaults", "encoder_port"], "")
        )

        offset_frame = tkinter.Frame(
            self,
        )
        offset_frame.pack(
            fill=tkinter.BOTH, expand=False, side=tkinter.LEFT, pady=0, padx=(20, 0)
        )
        compass_offset_label_label = tkinter.Label(
            offset_frame, text="Compass offset: ", font=tkinter.font.Font(size=8)
        )
        compass_offset_label_label.grid(column=0, row=0, pady=0)
        self.compass_offset_label = tkinter.Label(
            offset_frame,
            text=f"{(compass_offset * 180 / np.pi):.2f}°",
            font=tkinter.font.Font(size=8),
        )
        self.compass_offset_label.grid(column=1, row=0, pady=0)
        encoder_offset_label_label = tkinter.Label(
            offset_frame, text="Encoder offset: ", font=tkinter.font.Font(size=8)
        )
        encoder_offset_label_label.grid(column=0, row=1, pady=0)
        self.encoder_offset_label = tkinter.Label(
            offset_frame,
            text=f"{(encoder_offset * 180 / np.pi):.2f}°",
            font=tkinter.font.Font(size=8),
        )
        self.encoder_offset_label.grid(column=1, row=1, pady=0)

        self.set_offset_button = tkinter.Button(
            self, text="Set offsets", command=self.set_offsets
        )
        self.set_offset_button.pack(side=tkinter.LEFT)

        host_label = tkinter.Label(self, text="Spectrum channel:")
        host_label.pack(
            side=tkinter.LEFT, fill=tkinter.NONE, padx=(20, 5), pady=10, expand=False
        )

        # self.channel_spectrum_combo_string =
        self.channel_spectrum_combo = ttk.Combobox(self, width=1)
        self.channel_spectrum_combo["values"] = [0, 1, 2, 3]
        self.channel_spectrum_combo.pack(side=tkinter.LEFT)
        self.channel_spectrum_combo.bind(
            "<<ComboboxSelected>>", self.choose_spectrum_commands
        )
        self.channel_spectrum_combo.configure(state="disabled")

        host_label = tkinter.Label(self, text="Host:")
        host_label.pack(
            side=tkinter.LEFT, fill=tkinter.NONE, padx=(60, 5), pady=10, expand=False
        )

        self.host_entry = tkinter.Entry(self, textvariable=self.host_address, width=15)
        self.host_entry.pack(side=tkinter.LEFT, padx=5, expand=False)

        encoder_port_label = tkinter.Label(self, text="Encoder port:")
        encoder_port_label.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=(10, 5), pady=10, expand=False
        )

        self.encoder_port_entry = tkinter.Entry(
            self, textvariable=self.encoder_port_string, width=8
        )
        self.encoder_port_entry.pack(side=tkinter.LEFT, padx=5, expand=False)
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
        self.send_commands_function = send_commands_function

    def connect_commands(self) -> None:
        self.connect_commands_function(self.host_address.get())

    def set_offsets(self) -> None:
        pass  # TODO

    def choose_spectrum_commands(self, event: Any) -> None:
        self.send_commands_function(
            f"DEBUG:SpectrumChannel! {self.channel_spectrum_combo.current()};"
        )
