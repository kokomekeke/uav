import tkinter
from tkinter import ttk
from typing import Any, Callable, Optional
from pysagax.source.source_manager import SourceManager

from pysagax.ui.custom_widgets import ComboboxWithLabel, EntryWithLabel
from pysagax.util.read_from_conf import read_from_conf
from pysagax.util.mat import si_to_float
from pysagax.ui.ui_helpers import en_if


class ControlFrame(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        conf: Optional[dict[str, Any]],
        do_configuration_function: Callable[[dict[str, Any]], None],
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
            1,
            read_from_conf(conf, ["defaults", "center_freq"], "446M"),
        )

        self.bw_entry = EntryWithLabel(
            self, "Bandwidth:", 0, 2, read_from_conf(conf, ["defaults", "bandwith"], "1M")
        )

        self.gain_entry = EntryWithLabel(
            self, "USRP Gain:", 0, 3, read_from_conf(conf, ["defaults", "gain"], "50")
        )

        bin_count_entry_label = ttk.Label(
            self, text="Bin count:"
        )  # TODO:separate bin count and burst stride setting?
        bin_count_entry_label.grid(column=0, row=4, sticky=tkinter.W, padx=5, pady=5)

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
            column=1, row=4, sticky=tkinter.E + tkinter.W, padx=5, pady=5
        )

        self.roi_center_entry = EntryWithLabel(
            self,
            "ROI center freq:",
            2,
            1,
            read_from_conf(conf, ["defaults", "roi_center"], "446.065M"),
        )

        self.roi_span_entry = EntryWithLabel(
            self, "ROI span:", 2, 2, read_from_conf(conf, ["defaults", "roi_span"], "50k")
        )

        self.roi_threshold_entry = EntryWithLabel(
            self,
            "ROI threshold:",
            2,
            3,
            read_from_conf(conf, ["defaults", "roi_threshold"], "-40"),
        )

        self.burst_stride_entry = EntryWithLabel(
            self,
            "Burst stride:",
            2,
            4,
            read_from_conf(conf, ["defaults", "burst_stride"], "50000"),
        )
        self.configure_button = tkinter.Button(
            self, text="Configure", command=self.configure_commands
        )
        self.configure_button.grid(
            column=3, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.configure_button.configure(state="disabled")
        self.do_configuration_function = do_configuration_function

    def path_update(self) -> None:
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
            "roi_center": si_to_float(self.roi_center_entry.get()),
            "roi_span": si_to_float(self.roi_span_entry.get()),
            "roi_threshold": self.roi_threshold_entry.get(),
        }
        self.do_configuration_function(**kwargs)
