import tkinter
from tkinter import ttk
from typing import Any, Callable, Optional, Sequence, Type


class ToggleButton(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        on_action: Callable[[], None],
        off_action: Callable[[], None],
        default_value: bool = True,
        *args: Any,
        **kwargs: Any,
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
        master: tkinter.Misc,
        labeltext: str,
        column: int,
        row: int,
        default_value: str = "",
        variable_type: Type[Any] = tkinter.StringVar,
        width: int = 11,
        padx: int = 5,
        pady: int = 5,
    ) -> None:
        """
        tkinter widget of a label, entry box and tkinter variable combined to be used in frames with columnconfigure
        """
        self.variable = variable_type(value=default_value)
        self.label = ttk.Label(master, text=labeltext)
        self.label.grid(column=column, row=row, sticky=tkinter.W, padx=padx, pady=pady)

        super().__init__(master, textvariable=self.variable, width=width)
        self.grid(
            column=column + 1,
            row=row,
            sticky=tkinter.E + tkinter.W,
            padx=padx,
            pady=pady,
        )

    def get(self) -> Any:
        return self.variable.get()

    def set(self, value: Any) -> Any:
        return self.variable.set(value=value)

    def destroy(self) -> None:
        self.label.destroy()
        return super().destroy()


class ComboboxWithLabel(EntryWithLabel, ttk.Combobox):
    def __init__(
        self,
        master: tkinter.Misc,
        labeltext: str,
        column: int,
        row: int,
        default_value: str = "",
        variable_type: Type[Any] = tkinter.StringVar,
        width: int = 11,
        padx: int = 5,
        pady: int = 5,
        value_options: Sequence[str] =[],
    ) -> None:
        super().__init__(
            master,
            labeltext,
            column,
            row,
            default_value,
            variable_type,
            width,
            padx,
            pady,
        )

        self["values"] = value_options
