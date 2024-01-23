import re
import tkinter
from tkinter import ttk
from typing import Any
import numpy as np

from numpy._typing import _16Bit

from pysagax.heading.heading_manager import HeadingManager
from pysagax.heading.heading_sources import HeadingStatic
from pysagax.ui.custom_widgets import EntryWithLabel
from pysagax.util.confreader import confreader


class HeadingSourceFrame(tkinter.Frame):
    def __init__(self, master: Any, heading_manager: HeadingManager, conf):
        super().__init__(master)
        self.heading_manager = heading_manager

        self.conf = conf

        self.type_string = tkinter.StringVar(value="Static")

        self.type_combo = ttk.Combobox(self, textvariable=self.type_string, width=11)
        self.type_combo["values"] = list(
            self.heading_manager.heading_source_types.keys()
        )
        self.type_combo.current(0)
        self.type_combo.bind("<<ComboboxSelected>>", self.select_new_source)
        self.type_combo.pack(fill=tkinter.X, expand=True)
        self.heading_manager.create(HeadingStatic(self.conf))
        self.config_vars: dict[str, tkinter.Variable] = {}
        self.reconfigure_button = tkinter.Button(self)
        self.config_frame = self.construct_settings_frame()
        self.config_frame.pack(fill=tkinter.BOTH, expand=True)

        self.offset_frame = self.construct_offset_frame()
        self.offset_frame.pack(side=tkinter.RIGHT, fill=tkinter.NONE, expand=False, padx=5, pady=5)

        self.pack()
        self.heading_manager.start()

    def update_configuration(self, *args: Any) -> bool:
        if self.heading_manager.heading_source is None:
            return False
        try:
            for (
                setting_key,
                setting_type,
            ) in self.heading_manager.heading_source.get_parameters().items():
                self.heading_manager.update_parameter(
                    setting_key, self.config_vars[setting_key].get()  # type: ignore
                )
        except KeyError:
            return False
        return True

    def reconf_commands(self) -> None:
        new_source = list(self.heading_manager.heading_source_types.values())[
            self.type_combo.current()
        ]
        self.heading_manager.create(new_source(self.conf))
        self.update_configuration()
        self.heading_manager.initialize()

    def select_new_source(self, e: Any) -> None:
        new_source = list(self.heading_manager.heading_source_types.values())[
            self.type_combo.current()
        ]
        self.heading_manager.create(new_source(self.conf))
        self.heading_manager.initialize()
        print(repr(self.heading_manager.heading_source))
        self.config_frame.destroy()
        self.config_frame = self.construct_settings_frame()
        self.config_frame.pack(fill=tkinter.BOTH, expand=True)

    def construct_settings_frame(self) -> tkinter.Frame:
        new_frame = tkinter.Frame(self)
        if self.heading_manager.heading_source is None:
            return new_frame
        row = 0
        new_frame.grid_rowconfigure(
            len(self.heading_manager.heading_source.get_parameters()), weight=1
        )  # this needed to be added
        new_frame.grid_columnconfigure(0, weight=1)  # as did this
        new_frame.grid_columnconfigure(1, weight=1)  # as did this
        for setting_key, [
            setting_type,
            default_value,
        ] in self.heading_manager.heading_source.get_parameters().items():
            label = tkinter.Label(
                new_frame,
                text=f"{setting_key}",
            )
            label.grid(column=0, row=row, pady=0)
            if setting_type in ["number", "text"]:
                self.config_vars[setting_key] = tkinter.StringVar(value=default_value)

                textbox = tkinter.Entry(
                    new_frame,
                    textvariable=self.config_vars[setting_key],
                    width=8,
                    validate="focusout",
                    validatecommand=self.update_configuration,
                )

                textbox.grid(column=1, row=row, sticky="nsew")
            elif setting_type in ["bool"]:
                self.config_vars[setting_key] = tkinter.BooleanVar(value=default_value)
                check = ttk.Checkbutton(
                    new_frame,
                    variable=self.config_vars[setting_key],
                    onvalue=True,
                    offvalue=False,
                    command=self.update_configuration,
                )
                check.grid(column=1, row=row, sticky="nsew")
            else:
                result = re.search(r"(\d+)-(\d+)", setting_type)
                if result:
                    v = tkinter.IntVar(value=default_value)
                    self.config_vars[setting_key] = v
                    scale = tkinter.Scale(
                        new_frame,
                        from_=int(result.group(1)),
                        to=int(result.group(2)),
                        variable=v,
                        resolution=1,
                        orient=tkinter.HORIZONTAL,
                        command=self.update_configuration,
                    )
                    scale.grid(column=1, row=row, sticky="nsew")

            row += 1
        self.reconfigure_button.destroy()
        self.reconfigure_button = tkinter.Button(
            new_frame, text="Reconfigure", command=self.reconf_commands
        )
        self.reconfigure_button.grid(column=0, columnspan=2, row=row)

        return new_frame

    def construct_offset_frame(self) -> tkinter.Frame:
        new_frame = tkinter.Frame(self)
        if self.heading_manager.heading_source is None:
            return new_frame
        new_frame.grid_columnconfigure(0, weight=1)
        new_frame.grid_columnconfigure(1, weight=1)
        new_frame.grid_columnconfigure(2, weight=1)
        default_offset = confreader(self.conf, ["heading", "offset"], 0)
        self.offset_entry = EntryWithLabel(new_frame, labeltext="Offset (degrees):", column=0, row=0, default_value=default_offset, width=5)
        self.set_offset_button = tkinter.Button(new_frame, text="set offset", command=self.set_offset_commands)
        self.set_offset_button.grid(column=2, row=0)

        return new_frame
    
    def set_offset_commands(self):
        if self.heading_manager.heading_source is None:
            return False
        offset = float(self.offset_entry.get()) * np.pi / 180
        self.heading_manager.update_parameter("offset", offset)
        return True