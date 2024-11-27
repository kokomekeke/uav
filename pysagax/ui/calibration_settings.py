import tkinter
from tkinter import ttk
from tktooltip import ToolTip
from typing import Any, Callable, Optional
from pysagax.source.source_manager import SourceManager

from pysagax.ui.custom_widgets import ComboboxWithLabel, EntryWithLabel, RepeatedEntry, SIPrefixDoubleVar
from pysagax.util.read_from_conf import read_from_conf
from pysagax.util.mat import si_to_float
from pysagax.ui.ui_helpers import en_if
import pysagax.message.command_pb2 as proto_cmd


class CalibrationSettingsFrame(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        send_command_function: Callable,
        # source_manager: SourceManager,
        conf: Optional[dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        # self.source_manager: SourceManager = source_manager
        self.send_command_function = send_command_function

        self.columnconfigure(0)
        self.columnconfigure(1)
        self.columnconfigure(2)
        self.columnconfigure(3)


        self.iq_rate_entry = EntryWithLabel(
            self,
            "IQ rate (Hz):",
            column=0,
            row=0,
            default_value="1.0M",
            variable_type=tkinter.StringVar,
        )

        self.center_freq_settings_frame = RepeatedEntry(
            self,
            entries_config={"Center freq": SIPrefixDoubleVar},
            default_new_tab_values={"Center freq": "432M"})

        self.center_freq_settings_frame.grid(row=1, column=0, columnspan=4, sticky="nw")

        self.indentifier_entry = EntryWithLabel(
            self,
            "Identifier",
            column=0,
            row=2,
            variable_type=tkinter.StringVar,
        )

        self.configure_button = tkinter.Button(
            self, text="Configure", command=self.configure_commands
        )
        self.configure_button.grid(
            column=2, row=3, padx=10, pady=5, sticky="ew", columnspan=2
        )


    def configure_commands(self):
        """sends config commands to uav"""

        cmd = proto_cmd.Command(
            instruction=proto_cmd.Instruction.CS_CALIBRATE_START,
            calib_command=self.generate_calib_command()
        )
        cmd.kind = proto_cmd.Command.WRITE

        self.send_command_function(cmd)
    
    def generate_calib_command(self):
        msg = proto_cmd.CalibrationCommand()
        msg.identifier = self.indentifier_entry.get()
        msg.calibration_freqs.iq_rate = int(si_to_float(self.iq_rate_entry.get()))
        for value in self.center_freq_settings_frame.get_values():
            msg.calibration_freqs.center_freqs.append(int(value["Center freq"]))
        return msg
