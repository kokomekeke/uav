#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 21/12/2022.
#
from __future__ import annotations

import argparse
import multiprocessing
import os
import re
import shutil
import tempfile
import threading
import time
import tkinter
import tkinter.font
from datetime import datetime
from tkinter import messagebox
from pathlib import Path
from tkinter import ttk, filedialog
from typing import Optional, Callable, Iterable, Any, Mapping

import PIL.ImageTk
from PIL import ImageTk, Image

parser = argparse.ArgumentParser(
    description="test measurement helper utility parameters"
)

parser.add_argument(
    "--tdms-dir",
    dest="tdms_dir",
    metavar="PATH",
    type=str,
    help="path for the tdms files",
    default=".",
)
parser.add_argument(
    "--octave-dir",
    dest="octave_dir",
    metavar="PATH",
    type=str,
    help="path for the octave files",
    default=".",
)
parser.add_argument(
    "--measurement-dir",
    dest="measurement_dir",
    metavar="PATH",
    type=str,
    help="destination path for the measurement files",
    default=".",
)
args = parser.parse_args()


def get_dir_list(dir_path: str, filt: Callable[[str], bool]) -> set[str]:
    return set(
        [
            os.path.realpath(os.path.join(dir_path, f))
            for f in os.listdir(dir_path)
            if os.path.isfile(os.path.join(dir_path, f)) and filt(f)
        ]
    )


def convert_bytes(num: float) -> str:
    """
    this function will convert bytes to MB.... GB... etc
    """
    for x in ["bytes", "kB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0
    return "%3.1f" % num


def convert_si(num: float) -> str:
    for x in ["", "k", "M", "G", "T"]:
        if num < 1000.0:
            return "%3.3f%s" % (num, x)
        num /= 1000.0
    return "%3.1f" % num


def find_with_re(pattern: str, text: str) -> Optional[str]:
    try:
        return next(re.finditer(pattern, text)).group(1)
    except StopIteration:
        return None


def find_num_with_re(pattern: str, text: str) -> Optional[str]:
    try:
        return convert_si(float(next(re.finditer(pattern, text)).group(1)))
    except StopIteration:
        return None


def generate_diagrams(octave_data_fn: str, tmp_dir_name: str) -> None:
    octave_commands = ""
    with open(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "cstestclient_octave_graphs.m"
        )
    ) as octave_file:
        octave_commands = octave_file.read()
    with open(
        os.path.join(tmp_dir_name, "cstestclient_octave_graphs_tmp.m"), "w"
    ) as octave_file_out:
        octave_file_out.write(f"load({repr(os.path.realpath(octave_data_fn))});\n")
        octave_file_out.write(octave_commands)
    current_cwd = os.getcwd()
    os.chdir(tmp_dir_name)
    print(tmp_dir_name)
    ret = os.system("octave --silent cstestclient_octave_graphs_tmp.m")
    if ret:
        messagebox.showwarning(
            "Octave error",
            "Octave error! \n * Make sure octave bin directory \n"
            "(C:\\Program Files\\GNU Octave\\Octave-8.1.0\\mingw64\\bin)\n"
            "is in the system PATH. \n * Octave data file must be in a correct format.\n "
            "* Check the console for further errors.",
        )
    os.chdir(current_cwd)
    print("created temporary directory", tmp_dir_name)


class FileWatcherThread(threading.Thread):
    def __init__(self, window: ClientWindow) -> None:
        super().__init__(daemon=True)
        self.window = window
        self.tdms_file_list: set[str] = get_dir_list(
            self.window.tdms_dir, lambda f: f.endswith(".tdms")
        )
        self.octave_file_list: set[str] = get_dir_list(
            self.window.octave_dir, lambda f: f.endswith(".txt") and "octave" in f
        )

    def run(self) -> None:
        super().run()
        while True:
            new_tdms_file_list = get_dir_list(
                self.window.tdms_dir, lambda f: f.endswith(".tdms")
            )
            new_octave_file_list: set[str] = get_dir_list(
                self.window.octave_dir, lambda f: f.endswith(".txt") and "octave" in f
            )
            tdms_diff = new_tdms_file_list.difference(self.tdms_file_list)
            if len(tdms_diff) > 0:
                new_tdms_file = tdms_diff.pop()
                self.window.update_tdms_file(new_tdms_file)
            octave_diff = new_octave_file_list.difference(self.octave_file_list)
            if len(octave_diff) > 0:
                new_octave_file = octave_diff.pop()
                self.window.update_octave_file(new_octave_file)

            self.tdms_file_list = new_tdms_file_list
            self.octave_file_list = new_octave_file_list

            time.sleep(0.5)


class ClientWindow(tkinter.Frame):
    def __init__(self) -> None:
        global args
        super().__init__()

        self.img1: Optional[Any] = None
        self.img2: Optional[Any] = None
        self.pack(fill=tkinter.BOTH, expand=1)

        self.octave_dir = os.path.abspath(args.octave_dir)
        self.tdms_dir = os.path.abspath(args.tdms_dir)

        self.meas_title_string = tkinter.StringVar(value="00_Example")
        self.measurement_dir_string = tkinter.StringVar(
            value=os.path.abspath(args.measurement_dir)
        )
        self.tdms_file_button_text = tkinter.StringVar(value="TDMS file")
        self.octave_file_button_text = tkinter.StringVar(value="Octave file")

        # ## STATUS FRAME

        bottom_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        bottom_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        self.status_label = tkinter.Label(
            bottom_frame,
            text=f"TDMS dir: {self.tdms_dir}, Octave dir: {self.octave_dir}",
        )
        self.status_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        # ## CONNECT FRAME

        top_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        top_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        host_command_label = tkinter.Label(top_frame, text="Measurement dir:")
        host_command_label.pack(
            side=tkinter.LEFT, fill=tkinter.NONE, padx=5, pady=10, expand=False
        )

        self.measurement_dir_entry = tkinter.Entry(
            top_frame, textvariable=self.measurement_dir_string
        )
        self.measurement_dir_entry.pack(
            side=tkinter.LEFT, fill=tkinter.X, padx=5, expand=True
        )

        self.dir_picker_button = tkinter.Button(
            top_frame, text="...", command=self.dir_picker_commands
        )
        self.dir_picker_button.pack(side=tkinter.RIGHT, padx=5, pady=5)

        main_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        main_frame.pack(fill=tkinter.BOTH, side=tkinter.TOP, expand=True)
        right_frame = tkinter.Frame(main_frame)
        right_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.RIGHT)

        files_frame = tkinter.Frame(right_frame, relief=tkinter.GROOVE, borderwidth=40)
        files_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        self.tdms_file_button = tkinter.Button(
            files_frame,
            command=self.tdms_file_picker_commands,
            textvariable=self.tdms_file_button_text,
        )
        self.tdms_file_button.pack(fill=tkinter.BOTH, expand=True, side=tkinter.BOTTOM)
        self.octave_file_button = tkinter.Button(
            files_frame,
            command=self.octave_file_picker_commands,
            textvariable=self.octave_file_button_text,
        )
        self.octave_file_button.pack(
            fill=tkinter.BOTH, expand=True, side=tkinter.BOTTOM
        )

        self.images_frame = tkinter.Frame(
            right_frame, relief=tkinter.GROOVE, borderwidth=10
        )
        self.images_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        self.image_panels: list[tkinter.Label] = []
        self.image_containers: list[PIL.ImageTk.PhotoImage] = []

        self.done_button = tkinter.Button(
            right_frame,
            text="Save",
            command=self.do_save,
            fg="blue",
            relief="raised",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        self.done_button.pack(
            fill=tkinter.X, expand=False, side=tkinter.BOTTOM, padx=30, pady=40
        )

        left_frame = tkinter.Frame(main_frame, relief=tkinter.RAISED, borderwidth=1)
        left_title_frame = tkinter.Frame(
            left_frame, relief=tkinter.RAISED, borderwidth=1
        )
        meas_title_label = tkinter.Label(left_title_frame, text="Title:")
        meas_title_label.pack(
            side=tkinter.LEFT, fill=tkinter.NONE, padx=5, pady=10, expand=False
        )

        self.meas_title_entry = tkinter.Entry(
            left_title_frame, textvariable=self.meas_title_string
        )
        self.meas_title_entry.pack(
            side=tkinter.LEFT, fill=tkinter.X, padx=5, expand=True
        )

        left_title_frame.pack(fill=tkinter.X, side=tkinter.TOP, expand=False)

        self.console_textarea = tkinter.Text(left_frame, height=6, width=60)
        self.console_textarea.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        self.clipboard_button = tkinter.Button(
            left_frame,
            text="Copy commands to clipboard",
            command=self.copy_to_clipboard_commands,
        )
        self.clipboard_button.pack(
            fill=tkinter.NONE, expand=False, side=tkinter.TOP, padx=5, pady=8
        )

        self.comments_textarea = tkinter.Text(
            left_frame, height=6, width=60, font=("TkDefaultFont", 10, "normal")
        )
        self.comments_textarea.pack(
            fill=tkinter.BOTH, expand=True, side=tkinter.BOTTOM, pady=10
        )

        left_frame.pack(fill=tkinter.BOTH, side=tkinter.LEFT, expand=True)

        if os.path.exists("example_cs_commands.txt"):
            with open("example_cs_commands.txt") as f:
                self.console_textarea.delete(1.0, tkinter.END)
                self.console_textarea.insert(
                    1.0, "\n".join([li.strip() for li in f.readlines()])
                )
        if os.path.exists("example_measurement_comments.md"):
            self.comments_textarea.delete(1.0, tkinter.END)
            self.comments_textarea.insert(
                1.0, Path("example_measurement_comments.md").read_text()
            )
        self.comments_textarea.bind("<KeyRelease>", self.refresh_markdown_editor)
        self.refresh_markdown_editor()

        self.file_watcher_thread = FileWatcherThread(window=self)
        self.file_watcher_thread.start()
        self.images_cache: list[tuple[str, bytes]] = []
        self.octave_file_path = ""
        self.tdms_file_path = ""

    def update_tdms_file(self, new_tdms_file: str) -> None:
        button_text = "TDMS File"
        if new_tdms_file:
            button_text += f"\n{os.path.basename(new_tdms_file)}\n{convert_bytes(os.path.getsize(new_tdms_file))}"
        self.tdms_file_button_text.set(button_text)
        self.tdms_file_path = new_tdms_file

    def update_octave_file(self, new_octave_file: str) -> None:
        button_text = "Octave File"
        if new_octave_file:
            button_text += f"\n{os.path.basename(new_octave_file)}\n{convert_bytes(os.path.getsize(new_octave_file))}"
        self.octave_file_button_text.set(button_text)
        self.octave_file_path = new_octave_file
        for existing_panel in self.image_panels:
            existing_panel.destroy()
        self.image_panels = []
        self.image_containers = []
        if not new_octave_file:
            return
        self.images_cache = []
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            generate_diagrams(new_octave_file, tmp_dir_name)
            png_files = [
                os.path.realpath(os.path.join(tmp_dir_name, f))
                for f in os.listdir(tmp_dir_name)
                if os.path.isfile(os.path.join(tmp_dir_name, f)) and f.endswith(".png")
            ]
            print(png_files)
            for png_file in png_files:
                img = Image.open(png_file)
                img = img.resize((250, 250), Image.LANCZOS)
                imgp = ImageTk.PhotoImage(img)
                self.image_containers.append(imgp)
                image_panel = tkinter.Label(self.images_frame, image=imgp)
                image_panel.pack(fill=tkinter.BOTH, expand=True, side=tkinter.LEFT)
                self.image_panels.append(image_panel)
                self.images_cache.append(
                    (os.path.basename(png_file), Path(png_file).read_bytes())
                )

    def dir_picker_commands(self) -> None:
        new_dir = filedialog.askdirectory(initialdir=self.measurement_dir_string.get())
        if new_dir:
            self.measurement_dir_string.set(new_dir)

    def tdms_file_picker_commands(self) -> None:
        new_file = filedialog.askopenfilename(
            initialdir=self.tdms_dir, filetypes=[("tdms", "*.tdms")]
        )
        if new_file:
            self.update_tdms_file(new_file)

    def octave_file_picker_commands(self) -> None:
        new_file = filedialog.askopenfilename(
            initialdir=self.octave_dir, filetypes=[("octave txt", "*.txt")]
        )
        if new_file:
            self.update_octave_file(new_file)

    def copy_to_clipboard_commands(self) -> None:
        root.clipboard_clear()
        root.clipboard_append(self.console_textarea.get("1.0", tkinter.END))

    def do_save(self) -> None:
        self.done_button.configure(state="disabled")
        save_path = os.path.join(
            self.measurement_dir_string.get(), self.meas_title_string.get()
        )
        if os.path.isdir(save_path):
            messagebox.showerror("Error", f"Directory {save_path} already exists!")
            self.done_button.configure(state="normal")
            return
        os.makedirs(save_path)
        print(f"Saving to {save_path}...")
        print("\tcommands.txt")
        Path(os.path.join(save_path, "commands.txt")).write_text(
            self.console_textarea.get("1.0", tkinter.END)
        )
        print("\tcomments.md")
        Path(os.path.join(save_path, "comments.md")).write_text(
            f"**Timestamp:** {datetime.now():%Y-%m-%d %H:%M:%S%z}  \n\n"
            + self.comments_textarea.get("1.0", tkinter.END)
        )
        if self.tdms_file_path:
            print(f"\t{os.path.basename(self.tdms_file_path)}")
            shutil.move(
                self.tdms_file_path,
                os.path.join(save_path, os.path.basename(self.tdms_file_path)),
            )
            self.update_tdms_file("")
        if self.octave_file_path:
            print(f"\t{os.path.basename(self.octave_file_path)}")
            shutil.move(
                self.octave_file_path,
                os.path.join(save_path, os.path.basename(self.octave_file_path)),
            )
            self.update_octave_file("")
        for image_name, image_binary in self.images_cache:
            print(f"\t{image_name}")
            Path(os.path.join(save_path, image_name)).write_bytes(image_binary)
        self.images_cache = []
        print("Making index")
        self.make_index()
        print("Done")
        self.done_button.configure(state="normal")

    def make_index(self) -> None:
        m_dir = self.measurement_dir_string.get()
        folders = [
            os.path.realpath(os.path.join(m_dir, f))
            for f in os.listdir(m_dir)
            if os.path.isdir(os.path.join(m_dir, f))
        ]
        doc = "# Measurements index  "
        for folder in folders:
            folder_path = os.path.join(m_dir, folder)
            doc += f"\n\n\n## {os.path.basename(folder)}"
            if os.path.exists(os.path.join(folder_path, "commands.txt")):
                commands_txt = Path(
                    os.path.join(folder_path, "commands.txt")
                ).read_text()
                iq_rate = find_num_with_re(r"SOURCE:BurstStride! (\d+)", commands_txt)
                center_freq = find_num_with_re(
                    r"SOURCE:CenterFrequency! (\d+)", commands_txt
                )
                bin_count = find_num_with_re(r"AOA:BinCount! (\d+)", commands_txt)
                burst_stride = find_num_with_re(
                    r"SOURCE:BurstStride! (\d+)", commands_txt
                )
                gains = [
                    find_with_re(rf"SOURCE:ChannelGain! {i} (\d+)", commands_txt)
                    for i in range(4)
                ]
                gains_str = [gain + "dB" if gain is not None else "?" for gain in gains]
                aoa_freq = find_num_with_re(r"ROI:CenterFrequency! (\d+)", commands_txt)
                aoa_span = find_num_with_re(r"ROI:Span! (\d+)", commands_txt)
                aoa_thres = find_num_with_re(r"ROI:Threshold! (\d+)", commands_txt)
                doc += "\n"
                doc += f"\n**IQ Rate:** {iq_rate}  " if iq_rate is not None else ""
                doc += (
                    f"\n**Center frequency:** {center_freq}  "
                    if center_freq is not None
                    else ""
                )
                doc += (
                    f"\n**Bin count:** {bin_count}  " if bin_count is not None else ""
                )
                doc += (
                    f"\n**Burst stride:** {burst_stride}  "
                    if burst_stride is not None
                    else ""
                )
                doc += f"\n**Gains:** {', '.join(gains_str)}  "
                doc += (
                    f"\n**AOA freq:** {aoa_freq}, **span:** {aoa_span}, **thres:** {aoa_thres}"
                    if aoa_freq and aoa_span and aoa_thres
                    else ""
                )

            if os.path.exists(os.path.join(folder_path, "comments.md")):
                doc += (
                    "\n\n" + Path(os.path.join(folder_path, "comments.md")).read_text()
                )

            png_files = [
                f
                for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f)) and f.endswith(".png")
            ]
            for png_file in png_files:
                doc += f"\n\n![{png_file}]({os.path.basename(folder_path)}/{png_file})"
        Path(os.path.join(m_dir, "index.md")).write_text(doc)

    def refresh_markdown_editor(self, *args: Any) -> None:
        styles = [
            (
                r"^#[a-zA-Z\s\d\?\!\.]+$",
                "Header 1",
                ("TkDefaultFont", 24, "bold"),
                "#000066",
            ),
            (
                r"^##[a-zA-Z\s\d\?\!\.]+$",
                "Header 2",
                ("TkDefaultFont", 16, "bold"),
                "#000066",
            ),
            (
                r"^###[a-zA-Z\s\d\?\!\.]+$",
                "Header 3",
                ("TkDefaultFont", 12, "bold"),
                "#000066",
            ),
            (
                r"^####[a-zA-Z\s\d\?\!\.]+$",
                "Header 4",
                ("TkDefaultFont", 11, "bold"),
                "#000066",
            ),
            (r"\*\*.+?\*\*", "Bold", ("TkDefaultFont", 10, "bold"), "#000000"),
            (r"\_.+?\_", "Italic2", ("TkDefaultFont", 10, "italic"), "#000000"),
            (r"^ \* ", "UList item", ("TkDefaultFont", 10, "bold"), "#660000"),
            (r"^ \d+. ", "OList item", ("TkDefaultFont", 10, "bold"), "#660000"),
            (r"`.+?`", "Code", "TkFixedFont", "#000000"),
        ]
        for pattern, name, font, color in styles:
            self.comments_textarea.tag_remove(name, "1.0", "end")
            matches = []
            text = self.comments_textarea.get("1.0", tkinter.END).splitlines()
            for i, line in enumerate(text):
                for match in re.finditer(pattern, line):
                    matches.append(
                        (f"{i + 1}.{match.start()}", f"{i + 1}.{match.end()}")
                    )

            for start, end in matches:
                self.comments_textarea.tag_add(name, start, end)

            self.comments_textarea.tag_config(name, font=font, foreground=color)  # type: ignore


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = ClientWindow()
    root.geometry("1024x768")
    root.wm_title("Measurement Helper Utility")
    root.mainloop()
