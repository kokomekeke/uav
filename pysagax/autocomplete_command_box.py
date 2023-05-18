import tkinter
from tkinter import Misc
from typing import Any, Callable, Optional


class AutocompleteCommandBox(tkinter.Frame):
    def __init__(self, master: Misc) -> None:
        super().__init__(master, relief=tkinter.RAISED, borderwidth=1)

        self.send_command_action: Optional[Callable[[], None]] = None
        self.command_string = tkinter.StringVar(value="")
        """
        Variable for the current value of the command box
        """
        self.command_entry = tkinter.Entry(self, textvariable=self.command_string)
        self.command_entry.pack(side=tkinter.TOP, fill=tkinter.X, padx=5, expand=True)
        self.command_suggestions_lb = tkinter.Listbox(self, height=3)

        self.command_suggestions_lb.pack(
            side=tkinter.TOP, fill=tkinter.X, padx=5, expand=False
        )

        self.command_suggestions = set()

    def initialize(self):
        self.command_entry.bind("<Return>", self.send_command_action)
        self.command_entry.bind("<KeyRelease>", self.suggestions_filter)
        self.command_entry.bind("<Tab>", self.autocomplete)
        self.command_entry.bind("<Down>", self.to_suggestions_list)
        self.command_entry.configure(state="disabled")

        self.command_suggestions_lb.bind(
            "<<ListboxSelect>>", self.select_suggestion_cmd
        )
        self.command_suggestions_lb.bind("<Tab>", self.to_command_box)
        self.command_suggestions_lb.bind("<Return>", self.to_command_box)
        self.command_suggestions_lb.bind("<Double-Button>", self.to_command_box)

    def add_to_suggestions(self, command: str):
        self.command_suggestions.add(command)
        # Also save fragments of commands
        if ":" in command:  # Save command group fragment.
            self.command_suggestions.add(command.split(":")[0] + ":")
        if "?" in command:  # Save command without arguments.
            self.command_suggestions.add(command.split("?")[0] + "?")
        if "!" in command:  # Save command without arguments.
            self.command_suggestions.add(command.split("!")[0] + "!")

    def get_sorted_commands(self) -> list[str]:
        command_history_sorted = list(self.command_suggestions)
        command_history_sorted.sort()
        return command_history_sorted

    def suggestions_filter(self, *args: Any) -> None:
        """
        Filter the suggestions box. Called when a letter is typed to the command input box.
        """
        self.command_suggestions_lb.delete(0, tkinter.END)  # Clear suggestions box
        command_history_sorted = list(self.command_suggestions)
        command_history_sorted.sort()
        typed_command_string = self.command_string.get()  # Typed in command (fragment)
        if ":" not in typed_command_string:
            # If no ":" yet, display only command beginning fragments
            command_history_sorted = list(
                filter(
                    lambda command: ":" not in command or command.endswith(":"),
                    command_history_sorted,
                )
            )
        if not ("?" in typed_command_string or "!" in typed_command_string):
            # Do not display commands with arguments, if the whole command has not been typed yet.
            command_history_sorted = list(
                filter(
                    lambda command: ("!" not in command and "?" not in command)
                    or command.endswith("!")
                    or command.endswith("?"),
                    command_history_sorted,
                )
            )
        for history_item in command_history_sorted:
            if history_item.upper().startswith(typed_command_string.upper()):
                self.command_suggestions_lb.insert(tkinter.END, history_item)

    def autocomplete(self, *args: Any) -> str:
        """
        Grab the first from the suggestions. Called on the Tab key.
        """
        self.command_string.set(self.command_suggestions_lb.get(0))
        self.command_entry.focus()
        self.command_entry.icursor(tkinter.END)
        return "break"

    def to_suggestions_list(self, *args: Any) -> str:
        """
        Move from the command input box to the suggestions list. Called on the Down key.
        """
        self.command_suggestions_lb.focus()
        self.command_string.set(self.command_suggestions_lb.get(0))
        return "break"

    def select_suggestion_cmd(self, *args: Any) -> None:
        """
        Select a command from the list and use it in the command input box.
        """
        if self.command_suggestions_lb.size() > 0:
            curselection = self.command_suggestions_lb.curselection()  # type: ignore
            # strange values when nothing selected
            if curselection not in [(), "", None]:
                self.command_string.set(
                    self.command_suggestions_lb.get(curselection[0])
                )

    def to_command_box(self, *args: Any) -> str:
        """
        Return from the command suggestion list to the command input box. Called on the Enter or Tab key.
        """
        self.command_entry.focus()
        self.command_entry.icursor(tkinter.END)
        self.suggestions_filter()
        return "break"

    def enable(self):
        self.command_suggestions_lb.configure(state="normal")
        self.command_entry.configure(state="normal")

    def disable(self):
        self.command_string.set("")
        self.command_suggestions_lb.configure(state="disabled")
        self.command_entry.configure(state="disabled")

    def focus(self):
        self.command_entry.focus()
