import tkinter
from tkinter import ttk
from tktooltip import ToolTip
from typing import Any, Callable, Optional, Sequence, Type
from pysagax.util.mat import si_to_float


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


class SIPrefixDoubleVar(tkinter.StringVar):
    def __init__(self, master = None, value = None, name = None):
        super().__init__(master, value, name)
    def get(self):
        return si_to_float(tkinter.StringVar.get())
class RepeatedEntry(tkinter.Frame):
    """
    GUI element for creating repeated entry fields.
    Provide the desired field types in a dictionary of displayed name ->  type
    Returns the entered values in a list of dicts.
    """

    def __init__(self,master,
                 entries_config: list[str] | dict[str, Any],
                 default_values: list[dict] = [],
                 default_new_tab_values: Optional[dict] = None,
                 reload_callback: Optional[callable] = None,
                 *args,
                 **kwargs):
        """
        entries_config: list of field name strings, or dict of field name string -> field type
        default_values: a list of dictionary representing the starting state
        default_new_tab_values: default values for a newly added tab
        reload_callback: a function to be called when pressing the reload button (eg for updating other gui elements too)
        
        """
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        if not isinstance(entries_config, dict):
            self._entries_config = {f: tkinter.StringVar for f in entries_config}
        else:
            self._entries_config = entries_config
        self._default_values = default_values
        self._default_new_tab_values = default_new_tab_values
        self._reload_callback = reload_callback


        tab_count_controls = tkinter.Frame(self)
        plus_button = tkinter.Button(
            tab_count_controls,
            text="+",
            command=self._repeated_field_plus,
        )
        plus_button.grid(row=0, sticky="n")
        minus_button = tkinter.Button(
            tab_count_controls,
            text="-",
            command=self._repeated_field_minus,
        )
        minus_button.grid(row=1, sticky="n")
        refresh_button = tkinter.Button(
            tab_count_controls,
            text="R",
            command=self._reload,
        )
        refresh_button.grid(row=2, sticky="n")
        ToolTip(
            refresh_button,
            msg="Reload values from config file \nor UAV's latest message",
            delay=1,
        )
        tab_count_controls.grid(row=0, column=0, sticky="nw")

        self._tabControl = ttk.Notebook(self)
        self._tabControl.grid(row=0, column=1)

    def update_defaults(self, new_defaults: Optional[list[dict]]):
        self._default_values = new_defaults if new_defaults is not None else []

    def get_values(self):
        values = []
        for i, tab_name in enumerate(self._tabControl.tabs()):
            tab = self._tabControl.nametowidget(tab_name)
            values.append({})
            for (name, vartype), entry in zip(self._entries_config.items(), tab._entries):
                if vartype == SIPrefixDoubleVar:
                    value = si_to_float(entry.get())
                else:
                    value = entry.get()
                values[i] |= {name: value}
        return values

    def _reload(self):
        # delete all tabs
        for i, tab_name in enumerate(self._tabControl.tabs()):
            tab = self._tabControl.nametowidget(tab_name)
            self._tabControl.forget(tab)

        if self._reload_callback is not None:
            self._reload_callback()

        # create new tabs 
        for values in self._default_values:
            i = self._tabControl.index(tkinter.END)
            tab = self._build_new_tab(values)
            self._tabControl.add(tab, text=f"[{i}]")
    
    def _build_new_tab(self, values: Optional[dict]=None):
        new_tab = self.SingleTab(self._tabControl, self._entries_config, values)
        new_tab.pack()
        return new_tab
    class SingleTab(tkinter.Frame):
        def __init__(
            self,
            master,
            entries_config,
            values = None,
            *args,
            **kwargs,
        ):
            tkinter.Frame.__init__(
                self,
                master,
                highlightbackground="gray",
                highlightthickness=1,
                *args,
                **kwargs,
            )
                    
            self._entries = []
            for i, (name, vartype) in enumerate(entries_config.items()):
                default_value = values[name] if values else None
                new_entry = EntryWithLabel(self, name, 0, i, default_value) 
                self._entries.append(new_entry)




    def _repeated_field_minus(self):
        i = self._tabControl.index(tkinter.END)

        if i >= 1:
            self._tabControl.forget(self._tabControl.tabs()[-1])

    def _repeated_field_plus(self):
        i = self._tabControl.index(tkinter.END)
        tab = self._build_new_tab(self._default_new_tab_values)
        self._tabControl.add(tab, text=f"[{i}]")

class ScrollableText(tkinter.Frame):
    """A tkinter widget that can display text from a stringvar and scrollable."""

    def __init__(
        self,
        master,
        textvariable,
        font="TkFixedFont",
        background="white",
        *args,
        **kwargs,
    ):
        super().__init__(master, *args, **kwargs)

        scrollbar = tkinter.Scrollbar(self, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        text = tkinter.Text(
            self,
            wrap="word",  # Wrap text by words, not characters
            font=font,
            background=background,
            state="disabled",  # Make it read-only
        )
        text.pack(side="left", expand=True, fill="both")

        # Attach scrollbar to Text widget
        scrollbar.config(command=text.yview)
        text.config(yscrollcommand=scrollbar.set)

        def update_text_widget():
            """updating textvariable triggers this function"""
            text.config(state="normal")
            text.delete(1.0, "end")
            text.insert("end", textvariable.get())
            text.config(state="disabled")

        # Attach stringvar trace to update Text
        textvariable.trace_add("write", update_text_widget)

        # Set initial text
        update_text_widget()


class PopupWindow(tkinter.Toplevel):
    """Popup Window base class that displays the content of the textvariable given and a close button."""

    def __init__(
        self,
        master,
        textvariable,
        title="Popup Window",
        on_close_callback=None,
        default_geometry="500x500",
        background="white",
        font="TkFixedFont",
        *args,
        **kwargs,
    ):
        super().__init__(master, *args, **kwargs)
        self.geometry(default_geometry)
        self.title(title)
        self.textvariable = textvariable

        text = ScrollableText(
            self,
            textvariable=self.textvariable,
            background=background,
            font=font,
        )
        self.close_button = tkinter.Button(self, text="Close", command=self.on_closing)
        self.close_button.pack(side="bottom", pady=10)

        text.pack(padx=10, pady=10, expand=True, fill="both")

        self._on_close_callback = on_close_callback
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.destroy()
        if self._on_close_callback is not None:
            self._on_close_callback()

    def bring_to_front(self):
        """Bring this window to front"""
        self.lift()
