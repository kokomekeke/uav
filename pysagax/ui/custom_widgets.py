import tkinter
from tkinter import ttk
from typing import Any, Optional


class ToggleButton(tkinter.Frame):
    def __init__(
        self, master, on_action, off_action, default_value=True, *args, **kwargs
    ) -> None:
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.on_action = on_action
        self.off_action = off_action

        self.switch_variable = tkinter.BooleanVar(value=default_value)
        off_button = tkinter.Radiobutton(
            self,
            text="Off",
            variable=self.switch_variable,
            indicatoron=False,
            value=False,
            width=8,
            command=self.off_action,
        )
        on_button = tkinter.Radiobutton(
            self,
            text="On",
            variable=self.switch_variable,
            indicatoron=False,
            value=True,
            width=8,
            command=self.on_action,
        )

        off_button.pack(side="left")
        on_button.pack(side="left")


class EntryWithLabel(ttk.Entry):
    def __init__(
        self,
        master,
        labeltext: str,
        column: int,
        row: int,
        default_value="",
        variable_type=tkinter.StringVar,
        width=11,
        padx=5,
        pady=5,
    ) -> None:
        """
        tkinter widget of a label, entry box and tkinter variable combined to be used in frames with columnconfigure
        """
        self.variable = variable_type(value=default_value)
        self.label = ttk.Label(master, text=labeltext)
        self.label.grid(column=column, row=row, sticky=tkinter.W, padx=padx, pady=pady)

        ttk.Entry.__init__(self, master, textvariable=self.variable, width=width)
        ttk.Entry.grid(
            self,
            column=column + 1,
            row=row,
            sticky=tkinter.E + tkinter.W,
            padx=padx,
            pady=pady,
        )

    def get(self):
        return self.variable.get()

    def set(self, value):
        return self.variable.set(value=value)
