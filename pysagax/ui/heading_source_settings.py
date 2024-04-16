import re
import tkinter
from tkinter import ttk
from typing import Any
import numpy as np

from numpy._typing import _16Bit

from pysagax.heading.heading_pb_client import HeadingPbClient
from pysagax.heading.heading_sources import HeadingStatic
from pysagax.ui.custom_widgets import EntryWithLabel
from pysagax.util.read_from_conf import read_from_conf


class HeadingSourceFrame(tkinter.Frame):
    def __init__(self, master: Any, heading_manager: HeadingPbClient, conf):
        super().__init__(master)
        self.heading_manager = heading_manager

        self.conf = conf

        self.type_string = tkinter.StringVar(value="Static")

        self.type_combo = ttk.Combobox(self, textvariable=self.type_string, width=11)
        self._ui_update_source_types()
        self.type_combo.bind("<<ComboboxSelected>>", self.select_new_source)
        self.type_combo.pack(fill=tkinter.X, expand=True)
        self.heading_manager.create("Static")
        self.config_vars: dict[str, tkinter.Variable] = {}
        self.reconfigure_button = tkinter.Button(self)
        self.config_frame = self.construct_settings_frame()
        self.config_frame.pack(fill=tkinter.BOTH, expand=True)

        self.offset_frame = self.construct_offset_frame()
        self.offset_frame.pack(
            side=tkinter.RIGHT, fill=tkinter.NONE, expand=False, padx=5, pady=5
        )

        self.pack()
        self.heading_manager.start()

    def _ui_update_source_types(self) -> None:
        source_types = list(self.heading_manager.get_heading_source_types())
        if len(source_types) == 0:
            source_types = ["Static"]
            self.type_combo.current(0)
        else:
            self.type_combo["values"] = list(source_types)
            self.type_combo.current(
                source_types.index(self.heading_manager.get_selected_source_type())
            )

    def update_configuration(self, *args: Any) -> bool:
        try:
            for (
                setting_key,
                setting_type,
            ) in self.heading_manager.get_parameters().items():
                self.heading_manager.update_parameter(
                    setting_key, self.config_vars[setting_key].get()  # type: ignore
                )
        except KeyError:
            return False
        return True

    def reconf_commands(self) -> None:
        self.heading_manager.create(
            self.heading_manager.get_heading_source_types()[self.type_combo.current()]
        )
        # self.update_configuration()
        self.heading_manager.initialize()

    def select_new_source(self, e: Any) -> None:
        self.heading_manager.create(
            self.heading_manager.get_heading_source_types()[self.type_combo.current()]
        )
        self.heading_manager.initialize()

    def update_ui(self) -> None:
        if self.heading_manager.ui_dirty():
            for child in self.config_frame.winfo_children():
                child.destroy()
            self.config_frame.destroy()
            self.config_frame = self.construct_settings_frame()
            self.config_frame.pack(fill=tkinter.BOTH, expand=True)

            for child in self.offset_frame.winfo_children():
                child.destroy()
            self.offset_frame.destroy()
            self.offset_frame = self.construct_offset_frame()
            self.offset_frame.pack(
                side=tkinter.RIGHT, fill=tkinter.NONE, expand=False, padx=5, pady=5
            )
        self._ui_update_source_types()

    def construct_settings_frame(self) -> tkinter.Frame:
        new_frame = tkinter.Frame(self)
        if self.heading_manager is None:
            return new_frame
        row = 0
        new_frame.grid_rowconfigure(
            len(self.heading_manager.get_parameters()), weight=1
        )  # this needed to be added
        new_frame.grid_columnconfigure(0, weight=1)  # as did this
        new_frame.grid_columnconfigure(1, weight=1)  # as did this
        print(f"e: {self.heading_manager.get_parameters()}")
        for setting_key, [
            setting_type,
            default_value,
        ] in self.heading_manager.get_parameters().items():
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
        if self.heading_manager is None:
            return new_frame
        new_frame.grid_columnconfigure(0, weight=1)
        new_frame.grid_columnconfigure(1, weight=1)
        new_frame.grid_columnconfigure(2, weight=1)
        default_offset = read_from_conf(self.conf, ["heading", "offset"], 0)
        self.offset_entry = EntryWithLabel(
            new_frame,
            labeltext="Offset (degrees):",
            column=0,
            row=0,
            default_value=default_offset,
            width=5,
        )
        self.set_offset_button = tkinter.Button(
            new_frame, text="set offset", command=self.set_offset_commands
        )
        self.set_offset_button.grid(column=2, row=0)

        return new_frame

    def set_offset_commands(self):
        if self.heading_manager is None:
            return False
        offset = float(self.offset_entry.get()) * np.pi / 180
        self.heading_manager.update_parameter("offset", offset)
        return True
