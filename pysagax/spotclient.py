#!/usr/bin/env python3

from __future__ import annotations

import argparse
import multiprocessing
import os
import queue
import re
import socket
import threading
import tkinter
from multiprocessing.managers import ValueProxy

from pysagax.heading.heading_manager import HeadingManager
from pysagax.heading.queue_collector import QueueValueCollector
from pysagax.spot.commands_connection_thread import CommandsConnectionThread
from pysagax.spot.commands_handler_thread import CommandsHandlerThread
from pysagax.spot.map_server import MapServer
from pysagax.spot.recording_thread import RecordingThread
from pysagax.spot.status_query_thread import StatusQueryThread
from pysagax.ui import HeadingSourceFrame
from pysagax.ui.connect_frame import ConnectFrame
from pysagax.ui.control_frame import ControlFrame
from pysagax.ui.playback_tab import PlaybackTab
from pysagax.ui.source_select_frame import SourceSelectFrame
from pysagax.ui.stat_frame import StatFrame
from pysagax.ui.status_frame import StatusFrame

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import traceback
from datetime import datetime
from time import sleep
from tkinter import ttk
from typing import Any, Callable, Literal, Optional

import numpy as np

import pysagax
from pysagax import (
    CoreServiceDebugPacket,
    CoreServiceEOFPacket,
    CoreServiceROIResultPacket,
    CoreServiceSpectrumPacket,
    StreamAndCompassProcess,
)
from pysagax.ui.plot_frame import PlotFrame, PlotSettingsFrame
from pysagax.util.multiqueue import MultiQueue
from pysagax.util.confreader import confreader

conf: Optional[dict[str, Any]] = None
icon_image: Optional[tkinter.PhotoImage] = None
root: Optional[tkinter.Misc] = None
ex: Optional[Client] = None


class ClientWindow(tkinter.Frame):
    def __init__(self, client: Client, root) -> None:
        self.do_stop = False

        # aggregated and current roi results, coming from StreaAndCompassProcess
        self.aggregated_roi_results = {
            "df_value_mean": None,
            "df_value_std": None,
            "df_elevation_mean": None,
            "df_elevation_std": None,
        }
        self.compass_angle = None
        self.compass_heading = None  # compass angle corrected with offset
        self.encoder_angle = None
        self.encoder_heading = None  # encoder angle corrected with offset

        tkinter.Frame.__init__(self, root)
        self.pack(side="top", fill=tkinter.BOTH, expand=True)

        self.client = client  # The GUI communicates with other components of the client through this reference

        self.status_frame = StatusFrame(
            master=self,
            map_server_start_callable=self.client.start_dfg_map_server,
            map_server_stop_callable=self.client.stop_dfg_map_server,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.status_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        self.connect_frame = ConnectFrame(
            master=self,
            conf=conf,
            send_commands_function=self.client.send_commands,
            connect_commands_function=self.connect_commands,
            disconnect_commands_function=self.disconnect_commands,
            logo_image=icon_image,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.connect_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        self.plot_frame = PlotFrame(self, conf, root)

        self.bottom_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        self.bottom_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.BOTTOM)

        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        self.left_notebook = ttk.Notebook(self.bottom_frame)
        self.source_select_frame = SourceSelectFrame(
            master=self.left_notebook,
            conf=conf,
            do_select_source_function=self.client.do_set_source_params,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.left_notebook.add(self.source_select_frame, text="Source Select")
        self.control_frame = ControlFrame(
            master=self.left_notebook,
            conf=conf,
            do_configuration_function=self.client.do_configuration_params,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.left_notebook.add(self.control_frame, text="Configuration")
        self.plot_settings_frame = PlotSettingsFrame(
            self.left_notebook,
            self.plot_frame,
            conf,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.left_notebook.add(self.plot_settings_frame, text="Plot Settings")
        self.heading_source_frame = HeadingSourceFrame(
            self.left_notebook, self.client.heading_manager, conf
        )
        self.left_notebook.add(self.heading_source_frame, text="Heading&GPS")
        self.left_notebook.pack(fill=tkinter.BOTH, expand=False, side=tkinter.LEFT)
        self.center_notebook = ttk.Notebook(self.bottom_frame)
        self.playback_tab = PlaybackTab(
            master=self.center_notebook,
            send_commands_function=self.client.send_commands,
        )
        self.playback_tab.start_local_recording_function = (
            self.client.start_local_recording
        )
        self.playback_tab.stop_local_recording_function = (
            self.client.stop_local_recording
        )
        self.playback_tab.abort_commands_function = self.client.abort_commands
        self.status_info_tab = ttk.Frame(self.center_notebook)
        self.stream_packets_tab = ttk.Frame(self.center_notebook)
        self.center_notebook.add(self.playback_tab, text="Playback")
        self.center_notebook.add(self.status_info_tab, text="Status info")
        self.center_notebook.add(self.stream_packets_tab, text="Stream packets")
        self.center_notebook.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True
        )

        center_box_width = confreader(conf, ["display", "center_box_width"], 60)
        self.status_info_lb = tkinter.Listbox(
            self.status_info_tab, height=4, width=center_box_width
        )
        status_info_lb_sb = tkinter.Scrollbar(self.status_info_tab, orient="horizontal")
        status_info_lb_sb.config(command=self.status_info_lb.xview)
        status_info_lb_sb.pack(side="bottom", fill=tkinter.X)
        self.status_info_lb.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True
        )

        self.stream_packets_lb = tkinter.Listbox(
            self.stream_packets_tab, height=4, width=center_box_width
        )
        stream_packets_lb_sb = tkinter.Scrollbar(
            self.stream_packets_tab, orient="horizontal"
        )
        stream_packets_lb_sb.config(command=self.stream_packets_lb.xview)
        stream_packets_lb_sb.pack(side="bottom", fill=tkinter.X)
        self.stream_packets_lb.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True
        )

        self.stat_frame = StatFrame(
            master=self.bottom_frame, relief=tkinter.RAISED, borderwidth=1, width=600
        )
        self.stat_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.RIGHT)

        self.packet_handler_thread = threading.Thread(
            target=self.gui_packet_handler, daemon=True
        )
        self.packet_handler_thread.start()

    def gui_packet_handler(self) -> None:
        while not self.do_stop:
            try:
                data = self.client.stream_to_gui_queue.get(timeout=0.2)

                packet = data["cs_packet"]
                self.aggregated_roi_results = data["aggregated_roi_results"]
                self.compass_angle = data["compass_angle"]
                self.compass_heading = data["compass_heading"]
                self.encoder_angle = data["encoder_angle"]
                self.encoder_heading = data["encoder_heading"]

                try:
                    ts = datetime.fromtimestamp(packet.time_ns / 1e9, tz=None)
                    packet_string = (
                        f"[{packet.stream_id}] {ts.strftime('%H:%M:%S')}.{int((packet.time_ns % 1e9) / 1e6):03d} - "
                        f"{str(packet)} - c_angle={self.compass_angle}; e_angle={self.encoder_angle}"
                    )
                    self.stream_packets_lb.insert(tkinter.END, packet_string)
                    self.stream_packets_lb.delete(
                        0, self.stream_packets_lb.size() - 1000
                    )
                    self.stream_packets_lb.see(tkinter.END)

                    if isinstance(packet, CoreServiceSpectrumPacket):
                        signal_db, noise_db = self.calculate_snr(packet)
                        self.stat_frame.snr_string.set(f"{signal_db-noise_db:.1f}dB")
                        self.plot_frame.plot_spectrum_packet(
                            packet, signal_db, noise_db
                        )

                    if isinstance(
                        packet, CoreServiceDebugPacket
                    ):  # updating peak plots
                        if packet.title == "peaks":
                            regex = r"peak(\d+)=(\d+)"
                            matches = re.findall(
                                regex, str(packet)
                            )  # creating a list of (ChannelID, PeakValue) tuples from the debug message
                            peaks = [peak[1] for peak in matches]
                            self.stat_frame.update_peak_plot(peaks)
                        elif packet.title == "q":
                            quality = float(packet.contents.decode().strip())
                            self.stat_frame.quality_value_string.set(f"{quality:.2f}")

                    if isinstance(packet, CoreServiceROIResultPacket):
                        latest_roi_resutls = {
                            "df_value": packet.roi_azimuth,
                            "df_elevation": packet.roi_elevation,
                        }

                        self.stat_frame.update_stats(
                            latest_roi_resutls, self.aggregated_roi_results
                        )

                    if isinstance(packet, CoreServiceEOFPacket):
                        self.info_update_handler(
                            "End of file reached for Sigmf recording",
                            source="GUI packet handler",
                        )
                        if self.client.repeat_playback:
                            self.client.send_commands(
                                "SOURCE:Position! 0;SOURCE:Start!;"
                            )
                except Exception as e:
                    if not self.do_stop:
                        print("[GUI packet handler]", e)
                        traceback.print_tb(e.__traceback__)
            except queue.Empty:
                pass
            except Exception as e:
                print("[GUI packet handler]", e)
                traceback.print_tb(e.__traceback__)
                return

    def command_status_msg_handler(self, message: str) -> None:
        if message.startswith("#info"):
            message = message[len("#info") :]
        elif message.startswith("#action"):
            message = message[len("#action") :]
            if message == "send_commands_finished":
                # self.decrease_unfinished_send_commands()
                return
        else:  # status updates have no prefix, these should also be shown on status_frame
            self.set_command_status(message)
        self.info_update_handler(message, "Command Thread")

    def stream_status_msg_handler(self, message: str) -> None:
        if message.startswith("#encoder"):
            message = message[len("#encoder") :]
            self.info_update_handler(message, source="Encoder")
        elif message.startswith("#compass"):
            message = message[len("#compass") :]
            self.info_update_handler(message, source="Compass")
            self.client.client_window.status_frame.status_compass_string.set(message)
        else:  # status updates have no prefix, these should also be shown on status_frame
            self.set_stream_status(message)
            self.info_update_handler(message, source="Stream Process")
        # TODO: update compass end map server in status_frame

    def recording_status_msg_handler(self, message: str) -> None:
        # if message.startswith("#info"):
        #     message = message[len("#info") :]
        # elif message.startswith("#action"):
        #     message = message[len("#action") :]
        #     if message == "send_commands_finished":
        #         self.decrease_unfinished_send_commands()
        #         return
        self.info_update_handler(message, "Recording Thread")

    def map_server_status_msg_handler(self, message: str) -> None:
        if message.startswith("#info"):
            message = message[len("#info") :]
            self.status_frame.status_map_server_string.set(message)
            return
        self.info_update_handler(message, "Map Server")

    def set_stream_status(self, message: str) -> None:
        try:
            self.status_frame.status_stream_string.set(message)
        except:
            pass  ##TODO: when exiting, this gets called after the window no longer exists

    def set_command_status(self, message: str) -> None:
        try:
            self.status_frame.status_command_string.set(message)
        except:
            pass  ##TODO: when exiting, this gets called after the window no longer exists

    def connect_commands(self, host_address: str) -> None:
        host_address = self.connect_frame.host_address.get()
        encoder_port = self.connect_frame.encoder_port_string.get()
        self.client.connect_commands(
            self.connect_action,
            self.connected_action,
            self.disconnect_action,
            host_address,
            encoder_port,
        )

    def disconnect_commands(self) -> None:
        self.client.disconnect_commands()

    def get_recording_paths(self) -> None:
        try:
            path_list = b""
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(
                    (self.connect_frame.host_address.get(), 12939)
                )  ##TODO port no. to args
                s.sendall(b"nc")
                while True:
                    data = s.recv(1024)
                    if not data:
                        break
                    path_list += data
            path_list_split = path_list.decode().split()
            path_list_stripped = sorted([path.strip() for path in path_list_split])
            self.source_select_frame.source_file_path_combo[
                "values"
            ] = path_list_stripped
        except Exception as e:
            print("[Updating recording paths]", e)

    def connected_action(self) -> None:
        get_recording_paths_thread = threading.Thread(
            target=self.get_recording_paths, daemon=True
        )
        get_recording_paths_thread.start()

    def connect_action(self) -> None:
        """
        Events triggered by successful connection
        """
        self.connect_frame.connect_button.configure(state="disabled")
        self.connect_frame.host_entry.configure(state="disabled")
        self.connect_frame.disconnect_button.configure(state="normal")
        self.connect_frame.channel_spectrum_combo.configure(state="normal")

        self.source_select_frame.configure_button.configure(state="normal")

        self.playback_tab.connected = True
        self.playback_tab.set_buttons_enabled()

    def disconnect_action(self) -> None:
        """
        Events triggered by client disconnect
        """
        try:
            self.connect_frame.disconnect_button.configure(state="disabled")
            self.connect_frame.host_entry.configure(state="normal")
            self.connect_frame.connect_button.configure(state="normal")
            self.connect_frame.channel_spectrum_combo.configure(state="disabled")

            self.control_frame.configure_button.configure(state="disabled")
            self.source_select_frame.configure_button.configure(state="disabled")

            self.playback_tab.connected = False
            self.playback_tab.set_buttons_enabled()
            self.disconnect_commands()  # to disconnect the other thread
        except:
            pass  # it might happen when closing the window
        try:
            if self.plot_frame.animation is not None:
                self.plot_frame.animation.event_source.stop()
        except Exception as e:
            pass

    def info_update_handler(
        self, update_string: str | list[str], source: Optional[str] = None
    ) -> None:
        if self.do_stop:  # this might happen when closing the window
            return
        if not isinstance(update_string, list):
            update_string = [update_string]
        for line in update_string:
            if source is not None:
                line = f"[{source}]: {line}"
            self.status_info_lb.insert(tkinter.END, line)
            self.status_info_lb.delete(0, self.stream_packets_lb.size() - 1000)
            self.status_info_lb.see(tkinter.END)
            print(datetime.now().strftime("%m.%d. %H:%M:%S"), line)

    def calculate_snr(self, packet: CoreServiceSpectrumPacket) -> tuple[float, float]:
        min_freq = packet.center_frequency - packet.iq_rate / 2
        max_freq = packet.center_frequency + packet.iq_rate / 2
        bin_freqs = np.linspace(min_freq, max_freq, packet.bin_count)

        spectrum = list(zip(bin_freqs, packet.magnitude_spectrum))

        roi_center = pysagax.si_to_float(self.control_frame.roi_center_entry.get())
        roi_span = pysagax.si_to_float(self.control_frame.roi_span_entry.get())
        roi_min = roi_center - roi_span / 2
        roi_max = roi_center + roi_span / 2

        signal_bins = [a for f, a in spectrum if roi_min < f and f < roi_max]
        noise_bins = [a for f, a in spectrum if not (roi_min < f and f < roi_max)]

        if len(signal_bins) == 0 or len(noise_bins) == 0:
            return 0, 0

        signal_db = max(signal_bins)
        noise_db = sum(noise_bins) / len(noise_bins)

        return signal_db, noise_db


# Owner class for the client
class Client:
    def __init__(self, root: Any) -> None:
        self.manager = multiprocessing.get_context("spawn").Manager()

        self.heading_manager = HeadingManager()
        self.stream_to_gui_queue: queue.Queue[Any] = self.manager.Queue(maxsize=100)
        self.stream_to_rec_queue: Optional[queue.Queue[Any]] = None
        self.stream_to_map_queue: queue.Queue[Any] = self.manager.Queue(maxsize=10)

        self.stream_process_multiqueue = MultiQueue([self.stream_to_gui_queue])

        self.client_window = ClientWindow(self, root)
        self.command_connection_thread: Optional[CommandsConnectionThread] = None
        self.command_thread: Optional[CommandsHandlerThread] = None
        self.status_query_thread: Optional[StatusQueryThread] = None
        self.stream_process: Optional[StreamAndCompassProcess] = None
        self.recording_thread: Optional[RecordingThread] = None
        self.dfg_map_server: Optional[MapServer] = None
        self.repeat_playback: bool = False

        self.stream_process_watcher_queue: multiprocessing.Queue[
            str
        ] = multiprocessing.Queue()
        self.command_thread_watcher_queue: multiprocessing.Queue[
            str
        ] = multiprocessing.Queue()
        self.recording_thread_watcher_queue: multiprocessing.Queue[
            str
        ] = multiprocessing.Queue()
        self.map_server_thread_watcher_queue: multiprocessing.Queue[
            str
        ] = multiprocessing.Queue()

        self.disconnect_value = self.manager.Value("i", 0)
        """
        Setting the '1' value of the disconnect_value multiprocessing variable will end the multiprocessing task on the
        next iteration.
        """

        self.mean_window_width_value: ValueProxy[float] = self.manager.Value(
            "float",
            confreader(conf, ["stats", "mean_window_width_seconds"], 0),
        )

        self.recording_started = False

        self.do_stop = False
        self.watcher_thread = threading.Thread(target=self.watcher_thread_fun)
        self.watcher_thread.start()

    def watcher_thread_fun(self) -> None:
        while not self.do_stop:
            try:
                do_sleep = True  # if every queue is empty -> sleep
                if self.stream_process is not None:
                    try:
                        msg = self.stream_process_watcher_queue.get_nowait()
                        self.client_window.stream_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass

                if self.command_thread is not None:
                    try:
                        msg = self.command_thread_watcher_queue.get_nowait()
                        self.client_window.command_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass

                if self.recording_thread is not None:
                    try:
                        msg = self.recording_thread_watcher_queue.get_nowait()
                        self.client_window.recording_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass
                if self.dfg_map_server is not None:
                    try:
                        msg = self.map_server_thread_watcher_queue.get_nowait()
                        self.client_window.map_server_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass
                if self.heading_manager is not None:
                    try:
                        msg = self.heading_manager.mp_status.get_nowait()
                        self.client_window.stream_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass

                ##TODO: msg_handler functions might not need separate threads
                if do_sleep:
                    sleep(0.1)
            except Exception as e:
                if not self.do_stop:
                    raise e
        ##TODO: empty and join watcher queues before terminating thread

    def abort_commands(self) -> None:
        """
        Send the command from the command entry box to the client. Called on pressing the Return key in the autocomplete box.
        """
        assert self.command_thread is not None
        if (
            self.command_connection_thread is None
        ):  ##TODO: After disconnecting command_thread should be None
            return
        self.command_thread.abort_commands()

    def send_commands(self, cmd: str) -> None:
        """
        Send the command from the command entry box to the client. Called on pressing the Return key in the autocomplete box.
        """
        assert self.command_thread is not None
        if (
            self.command_connection_thread is None
        ):  ##TODO: After disconnecting command_thread should be None
            return
        self.command_thread.enqueue_commands(cmd)

    def command_status_callback(self, working: bool, current_cmd: str) -> None:
        self.command_thread_watcher_queue.put("#action" + "send_commands_finished")
        self.client_window.playback_tab.command_status_callback(working, current_cmd)

    def start_dfg_map_server(self) -> None:
        global conf
        self.dfg_map_server = MapServer(
            self.stream_to_map_queue, self.map_server_thread_watcher_queue
        )
        self.stream_process_multiqueue.add_queue(self.stream_to_map_queue)

        self.dfg_map_server.host = confreader(conf, ["map_server", "host"], "0.0.0.0")
        self.dfg_map_server.port = confreader(conf, ["map_server", "port"], 20000)
        if "lat" in conf["map_server"] and "lon" in conf["map_server"]:
            self.dfg_map_server.predefined_coords = (
                conf["map_server"]["lat"],
                conf["map_server"]["lon"],
            )
        self.dfg_map_server.start()

    def stop_dfg_map_server(self) -> None:
        if isinstance(self.dfg_map_server, MapServer):
            self.dfg_map_server.run_thread = False

    def connect_commands(
        self,
        connect_action: Optional[Callable[[], None]],
        connected_action: Optional[Callable[[], None]],
        disconnect_action: Optional[Callable[[], None]],
        host_address: str,
        encoder_port: str = "",
    ) -> None:
        """
        Action of the "Connect" button
        """
        self.command_connection_thread = CommandsConnectionThread(
            self.command_thread_watcher_queue
        )
        self.command_connection_thread.connect_callback = connect_action
        self.command_connection_thread.connected_callback = connected_action
        self.command_connection_thread.disconnect_callback = disconnect_action
        self.command_connection_thread.host_port = f"{host_address}:12936"
        self.command_connection_thread.start()

        self.command_thread = CommandsHandlerThread(
            conn=self.command_connection_thread,
            status_callback=self.command_status_callback,
            status_queue=self.command_thread_watcher_queue,
        )

        self.command_thread.start()
        self.command_thread.set_response_handler(
            "CORE:Version?",
            lambda cmd, resp: self.command_thread_watcher_queue.put(
                f"#infoCS Version {resp[1]}.{resp[2]}.{resp[3]}"
                f"-{resp[4]}+{resp[5]} VCS:{resp[6]}"
            ),
        )
        self.command_thread.set_response_handler(
            "SOURCE:Configure!",
            lambda cmd, resp: self.command_thread_watcher_queue.put(
                "#infoCore Service configured"
                if int(resp[0]) == 0
                else "#infoCore Service conf failed"
            ),
        )
        self.command_thread.set_response_handler(
            "ROI:Configure!",
            lambda cmd, resp: self.command_thread_watcher_queue.put(
                "#infoCore Service ROI configured"
                if int(resp[0]) == 0
                else "#infoCore Service ROI failed"
            ),
        )
        self.command_thread.set_response_handler(
            "RECORDING:Stop!",
            lambda cmd, resp: self.command_thread_watcher_queue.put(
                f"#infoCS Recordings done: {', '.join(resp)}"
            ),
        )
        self.status_query_thread = StatusQueryThread(
            self.command_thread,
            self.client_window.playback_tab,
            self.client_window.control_frame,
        )
        self.status_query_thread.start()

        self.disconnect_value.value = False
        self.stream_process = StreamAndCompassProcess(
            self.stream_process_multiqueue,
            self.disconnect_value,
            self.stream_process_watcher_queue,
        )
        self.stream_process.heading_queue = QueueValueCollector(
            self.heading_manager.mp_values
        )
        self.stream_process.host_port = f"{host_address}:12937"
        self.stream_process.compass_host_port = f"{host_address}:12938"
        self.stream_process.encoder_port = encoder_port
        self.stream_process.mean_window_seconds = self.mean_window_width_value
        self.stream_process.use_sensor_fusion = confreader(
            conf, ["compass", "use_sensor_fusion"], False
        )
        self.stream_process.compass_offset = (
            confreader(conf, ["compass", "offset"], 0) * np.pi / 180
        )
        self.stream_process.start()

    def do_set_source_params(self, params: dict[str, Any]) -> None:
        self.do_set_source(**params)

    def do_set_source(
        self,
        from_file,
        source_file_path,
    ) -> None:
        if from_file:
            if source_file_path[-1] != "/":
                source_file_path = source_file_path + "/"
            self.send_commands(
                f"CORE:Version?;"
                f'SOURCE:Path! SigMF "{source_file_path}recording.sigmf-collection";SOURCE:Path?;'
            )
        else:
            self.send_commands(f"CORE:Version?;" f"SOURCE:Path! UHD;SOURCE:Path?;")

    def do_configuration_params(self, params: dict[str, Any]) -> None:
        self.do_configuration(**params)

    def do_configuration(
        self,
        freq,
        bw,
        gain,
        bin_count,
        burst_stride,
        roi_center,
        roi_span,
        roi_threshold,
    ) -> None:
        if self.status_query_thread.source_type == "UHD":
            source_dependent_commands = (
                f"SOURCE:CenterFrequency! {freq:.0f};"
                f"SOURCE:IqRate! {bw:.0f};"
                f"SOURCE:ChannelGain! 0 {gain};"
                f"SOURCE:ChannelGain! 1 {gain};"
                f"SOURCE:ChannelGain! 2 {gain};"
                f"SOURCE:ChannelGain! 3 {gain};"
            )
        elif self.status_query_thread.source_type == "SigMF":
            source_dependent_commands = f"SOURCE:Position! 0;"
        else:
            raise Exception(
                f"Unknown source type ({self.status_query_thread.source_type}) is used for by CoreService"
            )
        self.send_commands(
            f"CORE:Version?;"
            f"{source_dependent_commands}"
            f"AOA:BinCount! {bin_count};"
            f"SOURCE:BurstStride! {burst_stride};"
            f"SOURCE:Configure!;"
            f"AOA:Configure!;"
            f"ROI:Enable! 1;"
            f"ROI:CenterFrequency! {roi_center:.0f};"
            f"ROI:Span! {roi_span:.0f};"
            f"ROI:Threshold! {roi_threshold};"
            f"ROI:Configure!;"
        )

    def disconnect_commands(self) -> None:
        """
        Action of the "Disconnect" button
        """
        if self.command_connection_thread is not None:
            self.command_connection_thread.disconnect = True

        if self.stream_process is not None:
            if self.disconnect_value is not None:
                self.disconnect_value.value = True
        if self.dfg_map_server is not None:
            self.dfg_map_server.run_thread = False
            self.dfg_map_server.join()
        """ self.command_thread.join()
        self.stream_thread.join() """

    def update_roi_settings(self, roi_center, roi_span, roi_threshold) -> None:
        self.send_commands(
            f"ROI:CenterFrequency! {roi_center:.0f};"
            f"ROI:Span! {roi_span:.0f};"
            f"ROI:Threshold! {roi_threshold:.0f};"
            f"ROI:Configure!;"
        )

    def start_recording(self) -> None:
        self.start_local_recording()
        self.send_commands("RECORDING:Start!;")
        self.recording_started = True
        ##TODO: start local recording if CS is also recording when connecting to it

    def stop_recording(self) -> None:
        self.stop_local_recording()
        self.send_commands("RECORDING:Stop!;")
        self.recording_started = False

    def start_local_recording(self) -> None:
        self.stream_to_rec_queue = self.manager.Queue()  # TODO: set some large maxsize
        self.stream_process_multiqueue.add_queue(self.stream_to_rec_queue)
        self.recording_thread = RecordingThread(
            cs_packet_queue=self.stream_to_rec_queue,
            status_queue=self.recording_thread_watcher_queue,
        )
        self.recording_thread.start()

    def set_repeat(self, repeat_value: bool) -> None:
        self.repeat_playback = repeat_value

    def stop_local_recording(self) -> None:
        if self.recording_thread is not None:
            self.recording_thread.do_stop = True
        self.stream_process_multiqueue.remove_queue(self.stream_to_rec_queue)
        self.stream_to_rec_queue = None


def on_close() -> None:
    global root
    global ex
    assert ex is not None

    # dfg_map_server.run_thread = False
    ex.do_stop = True
    ex.client_window.do_stop = True
    ex.heading_manager.stop()
    ex.disconnect_commands()
    ex.client_window.quit()
    if root is not None:
        root.destroy()


def main() -> None:
    global ex
    global root
    global conf
    global icon_image
    parser = argparse.ArgumentParser(description="SPOTClient")
    parser.add_argument("config", nargs="?", default="spotclient.toml")
    args = parser.parse_args()
    conf = {}
    if os.path.isfile(args.config):
        print("Config file found")
        with open(args.config, "rb") as f:
            conf = tomllib.load(f)
        print(f"Config file loaded: {repr(conf)}")
    else:
        print("Config file not found")
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    icon_image_fn = "spot.png"
    if os.path.isfile(f"pysagax/{icon_image_fn}"):
        icon_image = tkinter.PhotoImage(file=f"pysagax/{icon_image_fn}")
    else:
        import importlib.resources

        icon_image = tkinter.PhotoImage(
            file=str(importlib.resources.files("pysagax").joinpath(icon_image_fn))
        )
    root.iconphoto(False, icon_image)
    root.geometry("1200x850")
    root.wm_title(f"SPOTClient {pysagax.__version__}")
    root.protocol("WM_DELETE_WINDOW", on_close)
    ex = Client(root)
    root.mainloop()


if __name__ == "__main__":
    main()
