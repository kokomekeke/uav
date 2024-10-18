import tkinter
from tkinter import ttk
from tktooltip import ToolTip
from typing import Any, Callable, Optional
from pysagax.source.source_manager import SourceManager

from pysagax.ui.custom_widgets import ComboboxWithLabel, EntryWithLabel
from pysagax.util.read_from_conf import read_from_conf
from pysagax.util.mat import si_to_float
from pysagax.ui.ui_helpers import en_if
import pysagax.message.command_pb2 as proto_cmd


class SingleROIEntry(tkinter.Frame):
    """Setting for a single element of the ROI mask. Diplayed in a tab of DetectionControlFrame"""

    def __init__(
        self,
        master,
        default_center_freq=None,
        default_span=None,
        default_threshold=None,
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

        self.roi_center_entry = EntryWithLabel(
            self, "Center freq:", 2, 1, default_center_freq
        )
        self.roi_span_entry = EntryWithLabel(self, "Span:", 2, 2, default_span)
        self.roi_threshold_entry = EntryWithLabel(
            self, "Threshold:", 2, 3, default_threshold
        )


class DetectionControlFrame(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        pp_configuration_function: Callable,
        *args: Any,
        **kwargs: Any,
    ):
        tkinter.Frame.__init__(self, master, *args, **kwargs)
        self.pp_configuration_function = pp_configuration_function

        self.columnconfigure(0)
        self.columnconfigure(1)
        self.columnconfigure(2)
        self.columnconfigure(3)

        roi_settings_frame = tkinter.Frame(self)

        tab_count_controls = tkinter.Frame(roi_settings_frame)
        plus_button = tkinter.Button(
            tab_count_controls,
            text="+",
            command=self.repeated_field_plus,
        )
        plus_button.grid(row=0, sticky="n")
        minus_button = tkinter.Button(
            tab_count_controls,
            text="-",
            command=self.repeated_field_minus,
        )
        minus_button.grid(row=1, sticky="n")
        refresh_button = tkinter.Button(
            tab_count_controls,
            text="R",
            command=self.display_latest_pp_config,
        )
        refresh_button.grid(row=2, sticky="n")
        ToolTip(
            refresh_button,
            msg="Load PostProcessing settings \n from UAV's latest message",
            delay=1,
        )
        tab_count_controls.grid(row=0, column=0, sticky="nw")

        self.tabControl = ttk.Notebook(roi_settings_frame)
        self.tabControl.grid(row=0, column=1)

        roi_settings_frame.grid(row=0, column=0, columnspan=4, sticky="nw")

        self.mean_window_entry = EntryWithLabel(
            self,
            "Mean window size (s):",
            column=0,
            row=1,
            default_value="1.0",
            variable_type=tkinter.IntVar,
        )

        self.configure_button = tkinter.Button(
            self, text="Configure", command=self.configure_commands
        )
        self.configure_button.grid(
            column=2, row=1, padx=10, pady=5, sticky="ew", columnspan=2
        )

        self.latest_pp_config = proto_cmd.PostProcessingConfig()

    def configure_commands(self):
        """sends config commands to uav (if updated by button or plot click)"""
        cmd = self.generate_pp_config_cmd()
        self.pp_configuration_function(cmd)

    def generate_pp_config_cmd(self) -> proto_cmd.PostProcessingConfig:
        """Generates a PostProcessingConfig message from the current settings"""
        msg = proto_cmd.PostProcessingConfig()
        msg.mean_window = max(float(self.mean_window_entry.get()), 0)
        for i, tab_name in enumerate(self.tabControl.tabs()):
            tab = self.tabControl.nametowidget(tab_name)
            roi = proto_cmd.ROIMask(
                roi_id=i,
                center_frequency=si_to_float(tab.roi_center_entry.get()),
                span=si_to_float(tab.roi_span_entry.get()),
                threshold=float(tab.roi_threshold_entry.get()),
            )
            msg.roi.append(roi)
        return msg

    def handle_roi_click(self, center_freq, threshold) -> None:
        "Changes values in currently visible ROI tab then sends config command with the updated values"
        if len(self.tabControl.tabs()) < 1:
            return
        current_tab_name = self.tabControl.select()
        current_tab = self.tabControl.nametowidget(current_tab_name)

        current_tab.roi_center_entry.set(f"{center_freq/1e6:.3f}M")
        current_tab.roi_threshold_entry.set(f"{threshold:.1f}")

        self.configure_commands()

    def update_pp_settings(self, pp_config: proto_cmd.PostProcessingConfig):
        """Store the latest pp config so it can be displayed on the gui if wanted"""
        self.latest_pp_config = pp_config
        # TODO: send pp_config by pysagax-uav for config read messages

    def display_latest_pp_config(self):
        # delete all tabs
        for i, tab_name in enumerate(self.tabControl.tabs()):
            tab = self.tabControl.nametowidget(tab_name)
            self.tabControl.forget(tab)

        self.mean_window_entry.set(self.latest_pp_config.mean_window)
        # create new tabs from ppconfig
        for roi in self.latest_pp_config.roi:
            i = self.tabControl.index(tkinter.END)
            tab = self.build_roi_tab(roi.center_frequency, roi.span, roi.threshold)
            self.tabControl.add(tab, text=f"[{i}]")

    def repeated_field_minus(self):
        i = self.tabControl.index(tkinter.END)

        if i >= 1:
            self.tabControl.forget(self.tabControl.tabs()[-1])

    def repeated_field_plus(self):
        i = self.tabControl.index(tkinter.END)
        tab = self.build_roi_tab()
        self.tabControl.add(tab, text=f"[{i}]")

    def build_roi_tab(self, center_freq="446.065M", span="50k", threshold="-40"):
        tab = SingleROIEntry(self.tabControl, center_freq, span, threshold)
        tab.pack()
        return tab


class ControlFrame(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        conf: Optional[dict[str, Any]],
        do_configuration_function: Callable[[dict[str, Any]], None],
        pp_configuration_function: Callable,
        source_manager: SourceManager,
        *args: Any,
        **kwargs: Any,
    ):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.source_manager: SourceManager = source_manager

        self.bin_count_string = tkinter.StringVar(
            value=read_from_conf(conf, ["defaults", "bin_count"], 1024)
        )

        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=2)
        self.columnconfigure(3, weight=1)

        self.freq_entry = EntryWithLabel(
            self,
            "Frequency:",
            0,
            0,
            read_from_conf(conf, ["defaults", "center_freq"], "446M"),
        )

        self.bw_entry = EntryWithLabel(
            self,
            "Bandwidth:",
            0,
            1,
            read_from_conf(conf, ["defaults", "bandwith"], "1M"),
        )

        self.gain_entry = EntryWithLabel(
            self, "USRP Gain:", 0, 2, read_from_conf(conf, ["defaults", "gain"], "50")
        )

        bin_count_entry_label = ttk.Label(
            self, text="Bin count:"
        )  # TODO:separate bin count and burst stride setting?
        bin_count_entry_label.grid(column=2, row=0, sticky=tkinter.W, padx=5, pady=5)

        bin_count_combo = ttk.Combobox(
            self, textvariable=self.bin_count_string, width=11
        )
        # TODO: bin count combo as EntryWithLabel
        bin_count_combo["values"] = [
            # Virgin monetary scale values.
            200,
            500,
            1000,
            2000,
            5000,
            10000,
            # Chad power of 2 values.
            0x80,
            0x100,
            0x200,
            0x400,
            0x800,
            0x1000,
            0x2000,
            0x4000,
            0x8000,
            0x10000,
            0x20000,
            0x40000,
            0x80000,
        ]
        bin_count_combo.grid(
            column=3, row=0, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        self.burst_stride_entry = EntryWithLabel(
            self,
            "Burst stride:",
            column=2,
            row=1,
            default_value=read_from_conf(conf, ["defaults", "burst_stride"], "50000"),
        )
        self.configure_button = tkinter.Button(
            self, text="Configure radio", command=self.configure_commands
        )
        self.configure_button.grid(
            column=0, row=4, padx=100, pady=5, sticky="ew", columnspan=4
        )
        self.configure_button.configure(state="disabled")
        self.do_configuration_function = do_configuration_function

        self.detection_control_frame = DetectionControlFrame(
            self, pp_configuration_function
        )
        self.detection_control_frame.grid(column=0, columnspan=4, row=6, sticky="wens")

    def config_update(self) -> None:
        self._update_bandwith_entry()
        tuning_settings_state = en_if(self.source_manager.current_source.is_tunable)
        self.freq_entry.config(state=tuning_settings_state)
        self.bw_entry.config(state=tuning_settings_state)
        self.gain_entry.config(state=tuning_settings_state)
        config_btn_state = en_if(self.source_manager.is_source_set())
        self.configure_button.configure(state=config_btn_state)

    def _update_bandwith_entry(self):
        # this could be implemented in EntryWithLabel to make it reusable
        bw_tuple = self.source_manager.current_source.bandwith_tuple
        if bw_tuple is None and isinstance(self.bw_entry, ComboboxWithLabel):
            # redraw as text entry
            self.bw_entry.destroy()
            self.bw_entry = EntryWithLabel(self, "Bandwidth:", 0, 2)
        elif bw_tuple is not None:
            if not isinstance(self.bw_entry, ComboboxWithLabel):
                # redraw as combobox
                self.bw_entry.destroy()
                self.bw_entry = ComboboxWithLabel(
                    self, "Bandwidth:", 0, 2, value_options=bw_tuple
                )
            elif self.bw_entry["values"] != bw_tuple:
                # update the list of bandwith options
                self.bw_entry["values"] = bw_tuple

    def configure_commands(self) -> None:
        kwargs = {
            "freq": si_to_float(self.freq_entry.get()),
            "bw": si_to_float(self.bw_entry.get()),
            "gain": self.gain_entry.get(),
            "bin_count": self.bin_count_string.get(),
            "burst_stride": self.burst_stride_entry.get(),
        }
        self.do_configuration_function(**kwargs)
