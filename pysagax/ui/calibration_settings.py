import tkinter
from tkinter import ttk
import tkinter.scrolledtext
from tktooltip import ToolTip
from typing import Any, Callable, Optional
from pysagax.source.source_manager import SourceManager

from pysagax.ui.custom_widgets import (
    ComboboxWithLabel,
    EntryWithLabel,
    PopupWindow,
    RepeatedEntry,
    SIPrefixDoubleVar,
)
from pysagax.util.read_from_conf import read_from_conf
from pysagax.util.mat import si_to_float
from pysagax.ui.ui_helpers import en_if
import pysagax.message.command_pb2 as proto_cmd

from google.protobuf import json_format


class LatestCalibrationResponseWindow(PopupWindow):
    def __init__(self, master, response_str, on_close_callback=None, *args, **kwargs):
        super().__init__(
            master=master,
            textvariable=response_str,
            title="Latest Calibration Values",
            on_close_callback=on_close_callback,
            background="white",
            font="TkFixedFont",
            *args,
            **kwargs,
        )


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
        self.latest_calibration_query_respone = tkinter.StringVar(value="")
        self.latest_calibration_window: Optional[LatestCalibrationResponseWindow] = None

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
            default_new_tab_values={"Center freq": "432M"},
        )

        self.center_freq_settings_frame.grid(row=1, column=0, columnspan=4, sticky="nw")

        self.indentifier_entry = EntryWithLabel(
            self,
            "Identifier",
            column=0,
            row=2,
            variable_type=tkinter.StringVar,
        )

        self.configure_button = tkinter.Button(
            self, text="Calibrate", command=self.configure_commands
        )
        self.configure_button.grid(
            column=2, row=2, padx=10, pady=3, sticky="ew", columnspan=2
        )

        self.calibrate_abort_button = tkinter.Button(
            self, text="Abort Calibration", command=self.calibrate_abort_commands
        )
        self.calibrate_abort_button.grid(
            column=2, row=4, padx=10, pady=3, sticky="ew", columnspan=2
        )

        self.calib_file_identifier_entry = EntryWithLabel(
            self,
            "File Identifier",
            column=0,
            row=5,
            variable_type=tkinter.StringVar,
        )
        self.read_from_file_button = tkinter.Button(
            self, text="Load From File", command=self.read_from_file_commands
        )
        self.read_from_file_button.grid(
            column=2, row=5, padx=10, pady=3, sticky="ew", columnspan=2
        )

        self.query_calib_values_button = tkinter.Button(
            self,
            text="Query Calibration Values",
            command=self.query_calib_values_commands,
        )
        self.query_calib_values_button.grid(
            column=2, row=6, padx=10, pady=5, sticky="ew", columnspan=2
        )

        self.phase_check_button = tkinter.Button(
            self, text="Calibration Phase Check", command=self.phase_check_commands
        )
        self.phase_check_button.grid(
            column=0, row=6, padx=10, pady=5, sticky="ew", columnspan=2
        )

        self.compensate_with_pahesdiffs_stop_button = tkinter.Button(
            self,
            text="Compensation ON",
            command=self.turn_compenstaion_on_commands,
        )
        self.compensate_with_pahesdiffs_stop_button.grid(
            column=0, row=8, padx=10, pady=5, sticky="ew", columnspan=2
        )

        self.compensate_with_pahesdiffs_stop_button = tkinter.Button(
            self,
            text="Compensation OFF",
            command=self.turn_compenstaion_off_commands,
        )
        self.compensate_with_pahesdiffs_stop_button.grid(
            column=2, row=8, padx=10, pady=5, sticky="ew", columnspan=2
        )

    def configure_commands(self):
        """sends config commands to uav"""

        cmd = proto_cmd.Command(
            instruction=proto_cmd.Instruction.CS_CALIBRATE_START,
            calib_command=self.generate_calib_command(),
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

    def calibrate_abort_commands(self):
        cmd = proto_cmd.Command(
            kind=proto_cmd.Command.WRITE,
            instruction=proto_cmd.Instruction.CS_CALIBRATE_ABORT,
        )
        self.send_command_function(cmd)

    def read_from_file_commands(self):
        cmd = proto_cmd.Command(
            kind=proto_cmd.Command.WRITE,
            instruction=proto_cmd.Instruction.CS_READ_PHASEDIFFS_FROM_FILE,
        )
        cmd.calib_command.identifier = self.calib_file_identifier_entry.get()
        self.send_command_function(cmd)

    def query_calib_values_commands(self):
        cmd = proto_cmd.Command(
            kind=proto_cmd.Command.WRITE,
            instruction=proto_cmd.Instruction.CS_CALIBRATION_VALUES_QUERY,
        )
        self.send_command_function(cmd)

    def phase_check_commands(self):
        cmd = proto_cmd.Command(
            kind=proto_cmd.Command.WRITE,
            instruction=proto_cmd.Instruction.CS_CALIBRATION_PHASE_CHECK,
        )
        self.send_command_function(cmd)

    def turn_compenstaion_on_commands(self):
        cmd = proto_cmd.Command(
            kind=proto_cmd.Command.WRITE,
            instruction=proto_cmd.Instruction.CS_TURN_ON_COMPENSATION,
        )
        self.send_command_function(cmd)

    def turn_compenstaion_off_commands(self):
        cmd = proto_cmd.Command(
            kind=proto_cmd.Command.WRITE,
            instruction=proto_cmd.Instruction.CS_TURN_OFF_COMPENSATION,
        )
        self.send_command_function(cmd)

    def qurey_calib_values_response_handler(self, response: proto_cmd.Response):
        """Handler callback for CS_CALIBRATION_VALUES_QUERY command responses"""
        self.latest_calibration_query_respone.set(str(response))
        # self.latest_calibration_query_respone.set(str(json_format.MessageToJson(response)))
        self.open_latest_calib_window()

    def open_latest_calib_window(self):
        if self.latest_calibration_window is not None:
            self.latest_calibration_window.bring_to_front()
            return
        self.latest_calibration_window = LatestCalibrationResponseWindow(
            self,
            self.latest_calibration_query_respone,
            self.on_latest_calib_window_closed,
        )

    def on_latest_calib_window_closed(self):
        self.latest_calibration_window = None
