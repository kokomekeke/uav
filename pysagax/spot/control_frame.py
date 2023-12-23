import tkinter
from tkinter import ttk
from typing import Any, Callable, Optional

from pysagax.ui.custom_widgets import EntryWithLabel
from pysagax.util.mat import si_to_float


class ControlFrame(tkinter.Frame):
    def __init__(
        self,
        master: tkinter.Misc,
        conf: Optional[dict[str, Any]],
        do_configuration_function: Callable[[dict[str, Any]], None],
        *args: Any,
        **kwargs: Any,
    ):
        tkinter.Frame.__init__(self, master, *args, **kwargs)

        self.path_string = tkinter.StringVar(value="No Source")

        self.bin_count_string = tkinter.StringVar(
            value=(conf["defaults"]["bin_count"] if conf else "")
        )
        self.source_file_path_string = tkinter.StringVar(value="")

        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=2)
        self.columnconfigure(3, weight=1)

        path_label = ttk.Label(self, textvariable=self.path_string)
        path_label.grid(column=0, row=0, columnspan=4, padx=5, pady=5)

        self.freq_entry = EntryWithLabel(
            self, "Frequency:", 0, 1, (conf["defaults"]["center_freq"] if conf else "")
        )

        self.bw_entry = EntryWithLabel(
            self, "Bandwidth:", 0, 2, (conf["defaults"]["bandwith"] if conf else "")
        )

        self.gain_entry = EntryWithLabel(
            self, "USRP Gain:", 0, 3, (conf["defaults"]["gain"] if conf else "")
        )

        bin_count_entry_label = ttk.Label(
            self, text="Bin count:"
        )  # TODO:separate bin count and burst stride setting?
        bin_count_entry_label.grid(column=0, row=4, sticky=tkinter.W, padx=5, pady=5)

        bin_count_combo = ttk.Combobox(
            self, textvariable=self.bin_count_string, width=11
        )
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
            (conf["defaults"]["roi_center"] if conf else ""),
        )

        self.roi_span_entry = EntryWithLabel(
            self, "ROI span:", 2, 2, (conf["defaults"]["roi_span"] if conf else "")
        )

        self.roi_threshold_entry = EntryWithLabel(
            self,
            "ROI threshold:",
            2,
            3,
            (conf["defaults"]["roi_threshold"] if conf else ""),
        )

        self.burst_stride_entry = EntryWithLabel(
            self,
            "Burst stride:",
            2,
            4,
            (conf["defaults"]["burst_stride"] if conf else ""),
        )
        self.configure_button = tkinter.Button(
            self, text="Configure", command=self.configure_commands
        )
        self.configure_button.grid(
            column=3, row=5, padx=10, pady=5, sticky=tkinter.E + tkinter.W
        )
        self.configure_button.configure(state="disabled")
        self.do_configuration_function = do_configuration_function

    def path_update(self, path: list[str]) -> None:
        self.path_string.set(
            " - ".join(
                part.replace("recording.sigmf-collection", "") for part in path[1:]
            )
        )
        if path[1].strip('"') == "UHD":
            self.freq_entry.config(state="enabled")
            self.bw_entry.config(state="enabled")
            self.gain_entry.config(state="enabled")
        else:
            self.freq_entry.config(state="disabled")
            self.bw_entry.config(state="disabled")
            self.gain_entry.config(state="disabled")

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
        self.do_configuration_function(kwargs)
