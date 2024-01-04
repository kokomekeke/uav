import tkinter
from tkinter import ttk
from typing import Any, Callable, Optional


class SourceSelectFrame(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        conf: Optional[dict[str, Any]],
        do_select_source_function: Callable[[dict[str, Any]], None],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        tkinter.Frame.__init__(self, master, *args, **kwargs)
        self.do_select_source_function = do_select_source_function
        # self.client: Client = self.master.master.master.client  ##??? todo
        self.source_file_path_string = tkinter.StringVar(value="")

        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=2)
        self.columnconfigure(3, weight=1)
        self.source_combo = ttk.Combobox(self, width=12)
        self.source_combo["values"] = ["USRP", "Generator", "Recording"]
        self.source_combo.current(0)
        self.source_combo.grid(
            column=0, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )
        self.source_combo.bind("<<ComboboxSelected>>", self.source_combo_update)

        self.source_file_path_combo = ttk.Combobox(
            self, textvariable=self.source_file_path_string, width=11, state="disabled"
        )
        self.source_file_path_combo.grid(
            column=1, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5, columnspan=3
        )

        self.configure_button = tkinter.Button(
            self, text="Set Source", command=self.configure_commands
        )
        self.configure_button.grid(
            column=3, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.configure_button.configure(state="disabled")

    def configure_commands(self) -> None:
        default_source_file_path = "/home/sagax/Generator/"
        if self.source_combo.current() == 1:
            source_file_path = default_source_file_path
        else:
            source_file_path = self.source_file_path_string.get()

        kwargs = {
            "from_file": self.source_combo.current() != 0,
            "source_file_path": source_file_path,
        }
        self.do_select_source_function(kwargs)

    def source_combo_update(self, event: Any) -> None:
        if self.source_combo.current() == 2:
            self.source_file_path_combo.config(state="enabled")
        else:
            self.source_file_path_combo.config(state="disabled")
