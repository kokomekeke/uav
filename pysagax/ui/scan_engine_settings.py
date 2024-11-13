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



class ManualTab(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        send_command_function: Callable,
        # source_manager: SourceManager,
        conf: Optional[dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ):

        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.send_command_function = send_command_function
        
        self.configure_button = tkinter.Button(
            self, text="Configure", command=self.configure_commands
        )
        self.configure_button.grid(
            column=2, row=3, padx=10, pady=5, sticky="ew", columnspan=2
        )
    
    def configure_commands(self):
        cmd = proto_cmd.Command(instruction=proto_cmd.Instruction.CONFIG)
        cmd.config.se.mode = proto_cmd.ScanEngineConfig.Mode.MANUAL
        self.send_command_function(cmd)

class ScanningTab(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        send_command_function: Callable,
        # source_manager: SourceManager,
        conf: Optional[dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ):

        tkinter.Frame.__init__(self, master, *args, **kwargs)


        self.range_settings_frame = RepeatedEntry(
            self,
            entries_config={"Start freq": SIPrefixDoubleVar,
                            "Stop freq": SIPrefixDoubleVar},
            default_new_tab_values={"Start freq": "442.5M",
                            "Stop freq": "443.5M"})
        self.range_settings_frame.grid(row=1, column=0, columnspan=4, sticky="nw")

        self.send_command_function = send_command_function
        
        self.configure_button = tkinter.Button(
            self, text="Configure", command=self.configure_commands
        )
        self.configure_button.grid(
            column=2, row=3, padx=10, pady=5, sticky="ew", columnspan=2
        )
    
    def configure_commands(self):
        cmd = proto_cmd.Command(instruction=proto_cmd.Instruction.CONFIG)
        cmd.config.se.mode = proto_cmd.ScanEngineConfig.Mode.SCANNING
        freq_ranges = self.range_settings_frame.get_values()
        for range in freq_ranges:
            proto_range = proto_cmd.FreqRange(start=range["Start freq"], stop=range["Stop freq"])
            cmd.config.se.scanning.ranges.append(proto_range)
        self.send_command_function(cmd)

class TrackingTab(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        send_command_function: Callable,
        # source_manager: SourceManager,
        conf: Optional[dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ):

        tkinter.Frame.__init__(self, master, *args, **kwargs)


        self.signals_settings_frame = RepeatedEntry(
            self,
            entries_config={"Frequency": SIPrefixDoubleVar,
                            "Bandwidth": SIPrefixDoubleVar},
            default_new_tab_values={"Frequency": "442.5M",
                            "Bandwidth": "1M"})
        self.signals_settings_frame.grid(row=1, column=0, columnspan=4, sticky="nw")

        self.send_command_function = send_command_function
        
        self.configure_button = tkinter.Button(
            self, text="Configure", command=self.configure_commands
        )
        self.configure_button.grid(
            column=2, row=3, padx=10, pady=5, sticky="ew", columnspan=2
        )
    
    def configure_commands(self):
        cmd = proto_cmd.Command(instruction=proto_cmd.Instruction.CONFIG)
        cmd.config.se.mode = proto_cmd.ScanEngineConfig.Mode.TRACKING
        signals = self.signals_settings_frame.get_values()
        for signal in signals:
            proto_signal = proto_cmd.TrackedSignal(frequency=signal["Frequency"], bandwidth=signal["Bandwidth"])
            cmd.config.se.tracking.signals.append(proto_signal)
        self.send_command_function(cmd)


class ScanEngineSettingsFrame(tkinter.Frame):
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


        self.mode_tabs = ttk.Notebook(self)
        self.mode_tabs.grid(row=0, column=1)

        self.manual_tab = ManualTab(self.mode_tabs, self.send_command_function)
        self.mode_tabs.add(self.manual_tab, text="Manual")

        self.scanning_tab = ScanningTab(self.mode_tabs, self.send_command_function)
        self.mode_tabs.add(self.scanning_tab, text="Scanning")

        self.tracking_tab = TrackingTab(self.mode_tabs, self.send_command_function)
        self.mode_tabs.add(self.tracking_tab, text="Tracking")


    # def configure_commands(self):
    #     """sends config commands to uav"""

    #     cmd = proto_cmd.Command(
    #         instruction=proto_cmd.Instruction.CS_CALIBRATE_START,
    #         calib_command=self.generate_calib_command()
    #     )

    #     self.send_command_function(cmd)
    
    # def generate_calib_command(self):
    #     msg = proto_cmd.CalibrationCommand()
    #     msg.identifier = self.indentifier_entry.get()
    #     msg.calibration_freqs.iq_rate = int(si_to_float(self.iq_rate_entry.get()))
    #     for i, tab_name in enumerate(self.tabControl.tabs()):
    #         tab = self.tabControl.nametowidget(tab_name)
    #         msg.calibration_freqs.center_freqs.append(
    #             si_to_float(tab.center_freq_entry.get())
    #         )
    #     return msg

    # def repeated_field_minus(self):
    #     i = self.tabControl.index(tkinter.END)
    #     if i >= 1:
    #         self.tabControl.forget(self.tabControl.tabs()[-1])

    # def repeated_field_plus(self):
    #     i = self.tabControl.index(tkinter.END)
    #     tab = self.build_center_freq_tab()
    #     self.tabControl.add(tab, text=f"[{i}]")

    # def build_center_freq_tab(self, center_freq="446.000M"):
    #     tab = SingleCenterFrequencyEntry(self.tabControl, center_freq)
    #     tab.pack()
    #     return tab







