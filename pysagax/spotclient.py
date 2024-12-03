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

from pysagax.communication.broadcast import RX
from pysagax.communication.req_rep_tcp import REQ
from pysagax.heading.heading_pb_client import HeadingPbClient
from pysagax.heading.queue_collector import QueueValueCollector
from pysagax.source.source_manager import CoreServiceStatus, SourceManager
from pysagax.spot.command_thread import CommandThread
from pysagax.spot.map_server import MapServer
from pysagax.spot.recording_thread import RecordingThread
from pysagax.spot.status_query_thread import StatusQueryThread
from pysagax.spot.stream_process import StreamProcess
from pysagax.ui.connect_frame import ConnectFrame
from pysagax.ui.control_frame import ControlFrame
from pysagax.ui.debug_tab import DebugTab
from pysagax.ui.heading_source_settings import HeadingSourceFrame
from pysagax.ui.calibration_settings import CalibrationSettingsFrame
from pysagax.ui.scan_engine_settings import ScanEngineSettingsFrame
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
import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading
from pysagax.message.data_types import DataType
from pysagax.ui.plot_frame import PlotFrame, PlotSettingsFrame
from pysagax.util.get_ip import get_ip
from pysagax.util.mat import yaw_pitch_roll_from_quaternion, has_close_elements
from pysagax.util.run_once import run_once
from pysagax.util.multiqueue import MultiQueue
from pysagax.util.read_from_conf import read_from_conf

conf: Optional[dict[str, Any]] = None
icon_image: Optional[tkinter.PhotoImage] = None
root: Optional[tkinter.Misc] = None
ex: Optional[Client] = None


class ClientWindow(tkinter.Frame):
    def __init__(self, client: Client, root) -> None:
        self.do_stop = False

        # aggregated and current roi results, coming from StreaAndCompassProcess
        self.detection_to_plot: proto_data.Detection | None = None
        self.heading_to_plot: proto_heading.HeadingData | None = None

        tkinter.Frame.__init__(self, root)
        self.pack(side="top", fill=tkinter.BOTH, expand=True)

        self.client = client  # The GUI communicates with other components of the client through this reference

        self.status_frame = StatusFrame(
            master=self,
            source_manager=self.client.source_manager,
            map_server_start_callable=self.client.start_dfg_map_server,
            map_server_stop_callable=self.client.stop_dfg_map_server,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.status_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        self.plot_frame = PlotFrame(self, conf, root, self.client.handle_roi_click)

        self.bottom_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        self.bottom_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.BOTTOM)

        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        self.left_notebook = ttk.Notebook(self.bottom_frame)
        self.connect_frame = ConnectFrame(
            master=self.left_notebook,
            conf=conf,
            connect_commands_function=self.connect_commands,
            disconnect_commands_function=self.intentional_disconnect_commands,
            logo_image=icon_image,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.left_notebook.add(self.connect_frame, text="Connect")
        self.source_select_frame = SourceSelectFrame(
            master=self.left_notebook,
            conf=conf,
            source_manager=self.client.source_manager,
            do_select_source_function=self.client.do_set_source,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.left_notebook.add(self.source_select_frame, text="Source Select")
        self.control_frame = ControlFrame(
            master=self.left_notebook,
            conf=conf,
            do_configuration_function=self.client.do_configuration,
            pp_configuration_function=self.client.config_pp_settings,
            source_manager=self.client.source_manager,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.left_notebook.add(self.control_frame, text="Configuration")
        self.plot_settings_frame = PlotSettingsFrame(
            self.left_notebook,
            self.plot_frame,
            send_commands_function=self.client.send_commands,
            conf=conf,
            relief=tkinter.RAISED,
            borderwidth=1,
        )
        self.left_notebook.add(self.plot_settings_frame, text="Plot Settings")
        self.heading_source_frame = HeadingSourceFrame(
            self.left_notebook, self.client.heading_manager, conf
        )
        self.calibration_settings_frame = CalibrationSettingsFrame(
            self.left_notebook, self.client.send_commands, conf
        )
        self.left_notebook.add(self.calibration_settings_frame, text="Calibration")
        self.scan_engine_settings_frame = ScanEngineSettingsFrame(
            self.left_notebook, self.client.send_commands, conf
        )
        self.left_notebook.add(self.scan_engine_settings_frame, text="Scan Engine")
        self.left_notebook.add(self.heading_source_frame, text="Heading&GPS")
        self.left_notebook.pack(fill=tkinter.BOTH, expand=False, side=tkinter.LEFT)
        self.center_notebook = ttk.Notebook(self.bottom_frame)
        self.playback_tab = PlaybackTab(
            master=self.center_notebook,
            send_commands_function=self.client.send_commands,
            source_manager=self.client.source_manager,
        )
        self.playback_tab.start_recording_function = self.client.start_recording
        self.playback_tab.stop_recording_function = self.client.stop_recording
        self.playback_tab.abort_commands_function = self.client.abort_commands

        self.debug_tab = DebugTab(
            master=self.center_notebook,
            send_commands_function=self.client.send_commands,
            abort_commands_function=self.client.abort_commands,
            source_manager=self.client.source_manager,
            client=self.client,
        )

        self.status_info_tab = ttk.Frame(self.center_notebook)
        self.stream_packets_tab = ttk.Frame(self.center_notebook)
        self.center_notebook.add(self.playback_tab, text="Playback")
        self.center_notebook.add(self.status_info_tab, text="Status info")
        self.center_notebook.add(self.stream_packets_tab, text="Stream packets")
        self.center_notebook.add(self.debug_tab, text="Debug")
        self.center_notebook.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=True
        )

        center_box_width = read_from_conf(conf, ["display", "center_box_width"], 60)
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

        self.packet_type_stats = {}
        self.packet_handler_thread = threading.Thread(
            target=self.gui_packet_handler, daemon=True
        )
        self.packet_handler_thread.start()

    def gui_packet_handler(self) -> None:
        while not self.do_stop:
            try:
                packet = self.client.stream_to_gui_queue.get(timeout=0.2)
                if self._is_packet_late(packet):
                    continue  # drop packet if we've already recieved a fresher one

                if isinstance(packet, proto_data.Measurement):
                    self.measurement_packet_handler(packet)
                elif isinstance(packet, proto_data.Telemetry):
                    self.telemetry_packet_handler(packet)
                else:
                    print(
                        f"Handling stream packet type {type(packet)} is not implemented"
                    )

            except queue.Empty:
                pass
            except Exception as e:
                print("[GUI packet handler]", e)
                traceback.print_tb(e.__traceback__)
                return

    def _is_packet_late(self, packet: proto_cmd):
        # keeps track of arrived packets
        # returns True if packet's timestamp is not fresher than all earlier arrived packets'
        # if the packet is more than 60s late, then we consider it as fresh (probably delayed system clock?)
        if type(packet) not in self.packet_type_stats.keys():
            self.packet_type_stats[type(packet)] = {
                "latest_ts": 0,
                "arrived": 0,
                "dropped": 0,
                "last_size_byte": 0,
            }

        self.packet_type_stats[type(packet)]["arrived"] += 1
        self.packet_type_stats[type(packet)]["last_size_byte"] = packet.ByteSize()

        timestamp = packet.time.seconds + packet.time.nanos / 1e9
        delay = self.packet_type_stats[type(packet)]["latest_ts"] - timestamp
        if delay > 0 and delay < 60:  # the packet is (reasonably) late
            self.packet_type_stats[type(packet)]["dropped"] += 1
            is_packet_late = True
        else:  # the packet is fresh, or more than 60s late -> keep it
            self.packet_type_stats[type(packet)]["latest_ts"] = timestamp
            is_packet_late = False

        self.debug_tab.update_stream_packet_stats(self.packet_type_stats)
        return is_packet_late

    def measurement_packet_handler(self, packet: proto_data.Measurement) -> None:
        self.update_stream_packet_lb(packet)

        # Storing latest heading and detection packets for PlotFrame to access
        self.heading_to_plot = packet.heading_data
        if len(packet.detection):
            # TODO: chose detection to show by roi_id
            self.detection_to_plot = packet.detection[0]
            signal_db = packet.detection[0].strength
            noise_db = signal_db - packet.detection[0].snr
        else:
            self.detection_to_plot = None
            signal_db, noise_db = 0, 0

        if len(packet.data):
            self.plot_frame.plot_spectrum_packet(packet.data[0], signal_db, noise_db)
            self._check_signal_close_to_center_freq(packet)

        self.stat_frame.update_peak_plot(packet.peaks)

        self.stat_frame.update_stats(
            self.detection_to_plot, self.heading_to_plot, packet.time
        )

    @run_once(timeout=10)
    def _check_signal_close_to_center_freq(self, packet):
        """notify user if a detection was made less than 10kHz away from a center frequency (excecutes once every 10 seconds)"""
        # TODO: maybe move this to PysagaxUAV
        if len(packet.detection):
            center_freqs = [
                s.center_frequency
                for s in packet.data
                if s.spectrum_type == proto_data.Spectrum.SpectrumType.MAGNITUDE
            ]
            if has_close_elements(
                center_freqs, [d.frequency for d in packet.detection], 1e4
            ):
                print("WARNING: center frequency is close to a detected signal!")

    def telemetry_packet_handler(self, packet: proto_data.Telemetry):
        # Processes telemetry packets that arrived through stream or command connection
        self.client.source_manager.source_telemetry_handler(packet)
        source_length = packet.source.length
        current_position = packet.source.position
        self.playback_tab.update(
            current_position=current_position, source_length=source_length
        )

    def update_stream_packet_lb(self, packet):
        ts = datetime.fromtimestamp(packet.time.seconds, tz=None)
        packet_string = (
            f"[{packet.stream_id}] {ts.strftime('%H:%M:%S')}.{int((packet.time.nanos % 1e9) / 1e6):03d} - "
            f"detection: {packet.detection}"
        )
        self.stream_packets_lb.insert(tkinter.END, packet_string)
        self.stream_packets_lb.delete(0, self.stream_packets_lb.size() - 1000)
        self.stream_packets_lb.see(tkinter.END)

    def command_status_msg_handler(self, message: str) -> None:
        if message.startswith("#info"):
            message = message[len("#info") :]
        elif message.startswith("#action"):
            message = message[len("#action") :]
        else:  # status updates have no prefix, these should also be shown on status_frame
            self.set_command_status(message)
        self.info_update_handler(message, "Command Thread")

    def stream_status_msg_handler(self, message: str) -> None:
        self.set_stream_status(message)
        self.info_update_handler(message, source="Stream Process")

    def recording_status_msg_handler(self, message: str) -> None:
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

    def connect_commands(
        self,
        host_address: str,
        host_cmd_port: int = 5556,
        client_stream_port: int = 4242,
    ) -> None:
        self.client.connect_commands(
            self.connect_action,
            self.connected_action,
            self.disconnect_action,
            host_address,
            host_cmd_port=host_cmd_port,
            client_stream_port=client_stream_port,
        )

    def intentional_disconnect_commands(
        self,
        host_address: str,
        host_cmd_port: int = 5556,
        client_stream_port: int = 4242,
    ):
        """When the user intentionally disconnects with the button, stop the stream
        before doing the same steps as when the client gets unintentionally disconnected
        """
        cmd = proto_cmd.Command(
            instruction=proto_cmd.STREAM_STOP, kind=proto_cmd.Command.WRITE
        )
        cmd.target.address = get_ip()
        cmd.target.port = client_stream_port
        self.client.send_commands(cmd)
        # If the connection is still working:
        # command_thread.do_disconnect should be called by the STREAM_STOP response handler

        def forced_disconnect():
            # If the STREAM_STOP response doesn't arrive within 1 sec
            # In this case we can't be sure if pysagaxUAV stopped the UDP stream to the client.
            sleep(1)
            if not self.client.command_thread.do_disconnect:
                print("WARNING: Forced disconnect")
                self.client.command_thread.do_disconnect = True

        threading.Thread(target=forced_disconnect, name="forced_disconnect").start()

    def disconnect_commands(self) -> None:
        self.client.disconnect_commands()

    def get_recording_paths(self) -> None:
        try:
            path_list = b""
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(
                    (self.connect_frame.host_entry.get(), 12939)
                )  ##TODO port no. to args
                s.sendall(b"nc")
                while True:
                    data = s.recv(1024)
                    if not data:
                        break
                    path_list += data
            path_list_split = path_list.decode().split()
            path_list_stripped = sorted([path.strip() for path in path_list_split])
            self.client.source_manager.update_recording_paths(path_list_stripped)
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
        self.connect_frame.connect_action()
        self.plot_settings_frame.channel_spectrum_combo.configure(state="normal")

        self.source_select_frame.configure_button.configure(state="normal")

        self.plot_frame.start_animation()

    def disconnect_action(self) -> None:
        """
        Events triggered by client disconnect
        """
        try:
            self.connect_frame.disconnect_action()
            self.plot_settings_frame.channel_spectrum_combo.configure(state="disabled")

            self.source_select_frame.configure_button.configure(state="disabled")

            self.disconnect_commands()  # to disconnect the other thread
        except:
            pass  # it might happen when closing the window
        self.plot_frame.stop_animation()

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


# Owner class for the client
class Client:
    def __init__(self, root: Any) -> None:
        self.manager = multiprocessing.get_context("spawn").Manager()

        self.source_manager = SourceManager()
        self.stream_to_gui_queue: queue.Queue[Any] = self.manager.Queue(maxsize=1)
        self.stream_to_rec_queue: Optional[queue.Queue[Any]] = None
        self.stream_to_map_queue: queue.Queue[Any] = self.manager.Queue(maxsize=1)

        self.stream_process_multiqueue = MultiQueue([self.stream_to_gui_queue])

        self.command_connection: Optional[REQ] = None
        self.command_thread: Optional[CommandThread] = None
        self.status_query_thread: Optional[StatusQueryThread] = None
        self.stream_process: Optional[StreamProcess] = None
        self.recording_thread: Optional[RecordingThread] = None
        self.dfg_map_server: Optional[MapServer] = None
        self.repeat_playback: bool = False

        self.heading_manager = HeadingPbClient(
            send_commands_function=self.send_commands,
            update_ui_callback=self.update_heading_ui,
        )
        self.client_window = ClientWindow(self, root)
        self.stream_process_watcher_queue: multiprocessing.Queue[str] = (
            multiprocessing.Queue()
        )
        self.command_connection_status_watcher_queue: multiprocessing.Queue[str] = (
            multiprocessing.Queue()
        )
        self.command_thread_watcher_queue: multiprocessing.Queue[str] = (
            multiprocessing.Queue()
        )
        self.recording_thread_watcher_queue: multiprocessing.Queue[str] = (
            multiprocessing.Queue()
        )
        self.map_server_thread_watcher_queue: multiprocessing.Queue[str] = (
            multiprocessing.Queue()
        )

        self.disconnect_value = self.manager.Value("i", 0)
        """
        Setting the '1' value of the disconnect_value multiprocessing variable will end the multiprocessing task on the
        next iteration.
        """

        self.mean_window_width_value: ValueProxy[float] = self.manager.Value(
            "float",
            read_from_conf(conf, ["stats", "mean_window_width_seconds"], 0),
        )

        self.recording_started = False

        self.do_stop = False
        self.watcher_thread = threading.Thread(target=self.watcher_thread_fun)
        self.watcher_thread.start()

    def update_heading_ui(self) -> None:
        self.client_window.heading_source_frame.update_ui()

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
                        msg = self.command_connection_status_watcher_queue.get_nowait()
                        self.client_window.command_status_msg_handler(msg)
                        do_sleep = False
                    except queue.Empty:
                        pass
                    try:
                        (
                            working,
                            current_cmd,
                        ) = self.command_thread_watcher_queue.get_nowait()
                        self.source_manager.command_status_callback(
                            working, current_cmd
                        )
                        self.client_window.playback_tab.display_command_status(
                            current_cmd
                        )
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
            self.command_connection is None
        ):  ##TODO: After disconnecting command_thread should be None
            return
        self.command_thread.abort_commands()

    def send_commands(self, cmd) -> None:
        """
        Send the command from the command entry box to the client. Called on pressing the Return key in the autocomplete box.
        """
        if self.command_thread is None:
            print(f"Unable to send command ({str(cmd)})")
            return
        if (
            self.command_connection is None
        ):  ##TODO: After disconnecting command_thread should be None
            return
        self.command_thread.enqueue_commands(cmd)

    def start_dfg_map_server(self) -> None:
        global conf
        self.dfg_map_server = MapServer(
            self.stream_to_map_queue, self.map_server_thread_watcher_queue
        )
        self.stream_process_multiqueue.add_queue(self.stream_to_map_queue)

        self.dfg_map_server.host = read_from_conf(
            conf, ["map_server", "host"], "0.0.0.0"
        )
        self.dfg_map_server.port = read_from_conf(conf, ["map_server", "port"], 20000)
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
        host_cmd_port: int = 5556,
        client_stream_port: int = 4242,
    ) -> None:
        """
        Action of the "Connect" button
        """

        self.command_connection = REQ(
            address_server=host_address, port_server=host_cmd_port
        )  # , address_client=None, port_client=5556, port_server=5555)

        self.command_thread = CommandThread(
            connection=self.command_connection,
            thread_status_queue=self.command_thread_watcher_queue,
            connection_status_queue=self.command_connection_status_watcher_queue,
        )
        self.command_thread.connect_callback = connect_action
        self.command_thread.connected_callback = connected_action
        self.command_thread.disconnect_callback = disconnect_action

        self.command_thread.start()

        self.command_thread.set_response_handler(
            proto_cmd.Instruction.PING,
            self.client_window.debug_tab.ping_response_handler,
        )
        self.command_thread.set_response_handler(
            proto_cmd.Instruction.CS_PING,
            self.client_window.debug_tab.cs_ping_response_handler,
        )
        self.command_thread.set_response_handler(
            proto_cmd.Instruction.CS_CALIBRATION_VALUES_QUERY,
            self.client_window.calibration_settings_frame.qurey_calib_values_response_handler,
        )
        self.command_thread.set_response_handler(
            proto_cmd.Instruction.STREAM_STOP,
            lambda response: setattr(self.command_thread, "do_disconnect", True),
        )  # set command_thread.do_disconnect to True (setattr() needed to do this in a lambda)

        self.disconnect_value.value = False

        all_groups = [group.value for group in DataType]
        self.stream_process = StreamProcess(
            client_stream_port,
            all_groups,
            self.stream_process_multiqueue,
            self.disconnect_value,
            self.stream_process_watcher_queue,
        )
        self.stream_process.start()

        self.status_query_thread = StatusQueryThread(client=self)
        self.status_query_thread.start()

        cmd_stream_start = proto_cmd.Command()
        cmd_stream_start.instruction = proto_cmd.STREAM_START
        # TODO: customazible stream levels
        cmd_stream_start.target.id = 1
        cmd_stream_start.target.level = proto_cmd.StreamTarget.StreamLevel.SPECTRUM
        cmd_stream_start.target.address = get_ip(host_address)
        cmd_stream_start.target.port = client_stream_port

        # TODO: think about ideal timeout values, move to config
        cmd_stream_start.target.heartbeat_timeout = 1
        cmd_stream_start.target.telemetry_timeout = 1

        self.command_thread.enqueue_commands(cmd_stream_start)
        return
        # TODO: the following response hanlder using protobuf
        self.command_thread.set_response_handler(
            "CORE:Version?",
            lambda cmd, resp: self.command_connection_status_watcher_queue.put(
                f"#infoCS Version {resp[1]}.{resp[2]}.{resp[3]}"
                f"-{resp[4]}+{resp[5]} VCS:{resp[6]}"
            ),
        )
        self.command_thread.set_response_handler(
            "SOURCE:Configure!",
            lambda cmd, resp: self.command_connection_status_watcher_queue.put(
                "#infoCore Service configured"
                if int(resp[0]) == 0
                else "#infoCore Service conf failed"
            ),
        )
        self.command_thread.set_response_handler(
            "ROI:Configure!",
            lambda cmd, resp: self.command_connection_status_watcher_queue.put(
                "#infoCore Service ROI configured"
                if int(resp[0]) == 0
                else "#infoCore Service ROI failed"
            ),
        )
        self.command_thread.set_response_handler(
            "RECORDING:Stop!",
            lambda cmd, resp: self.command_connection_status_watcher_queue.put(
                f"#infoCS Recordings done: {', '.join(resp)}"
            ),
        )

    def do_set_source(self, source: str, params: str) -> None:
        cmd = self.source_manager.get_set_source_command(source, params)
        self.command_thread.enqueue_commands(cmd)

    def do_configuration(self, freq, bw, gain, bin_count, burst_stride) -> None:
        cmd_list = self.source_manager.get_config_commands(
            freq, bw, gain, bin_count, burst_stride
        )
        self.send_commands(cmd_list)

    def disconnect_commands(self) -> None:
        """
        Action of the "Disconnect" button
        """
        if self.command_thread is not None:
            self.command_thread.do_disconnect = True
        if self.command_connection is not None:
            self.command_connection.disconnect()
            self.command_connection = None

        if self.stream_process is not None:
            if self.disconnect_value is not None:
                self.disconnect_value.value = True
        if self.dfg_map_server is not None:
            self.dfg_map_server.run_thread = False
            self.dfg_map_server.join()
        """ self.command_thread.join()
        self.stream_thread.join() """

    def config_pp_settings(self, pp_config: proto_cmd.PostProcessingConfig) -> None:
        # Constructs and sends a config message only containing PostProcessing info
        # Also calls PlotFrames's update roi plot function
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.CONFIG
        cmd.config.pp.CopyFrom(pp_config)

        self.send_commands(cmd)

        self.client_window.plot_frame.update_roi_graph(pp_config)

    def query_system_info(self):
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.INFO
        self.send_commands(cmd)

    def update_system_info(self, sysinfo: proto_cmd.SystemInfo) -> None:
        self.heading_manager.update_from_heading_status(sysinfo.heading)

    def handle_roi_click(self, center_freq, threshold) -> None:
        """update roi settings on gui with sending config commands"""
        self.client_window.control_frame.detection_control_frame.handle_roi_click(
            center_freq, threshold
        )

    def update_pp_settings(self, pp_config) -> None:
        """
        Update roi settings on gui WITHOUT sending config command
        Used when a config command gets answered by PysagaxUAV
        """
        self.client_window.control_frame.detection_control_frame.update_pp_settings(
            pp_config
        )

        self.client_window.plot_frame.update_roi_graph(pp_config)

    def start_recording(self) -> None:
        self.start_local_recording()
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.REC_START
        self.send_commands(cmd)
        self.recording_started = (
            True  # TODO: this is depracated (source_manager.recording_status)
        )
        ##TODO: start local recording if CS is also recording when connecting to it

    def stop_recording(self) -> None:
        self.stop_local_recording()
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.REC_STOP
        self.send_commands(cmd)
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


class Splash(tkinter.Toplevel):
    # FROM https://stackoverflow.com/a/38678891
    def __init__(self, parent):
        tkinter.Toplevel.__init__(self, parent)
        self.title("Loading")

        icon_image_fn = "spot.png"
        if os.path.isfile(f"pysagax/{icon_image_fn}"):
            self.icon_image = tkinter.PhotoImage(file=f"pysagax/{icon_image_fn}")
        else:
            import importlib.resources

            self.icon_image = tkinter.PhotoImage(
                file=str(importlib.resources.files("pysagax").joinpath(icon_image_fn))
            )

        self.icon_image_zoomed = self.icon_image.zoom(10, 10)
        self.icon_frame = tkinter.Frame(self, width=320, height=320)
        self.icon_frame.place(anchor="center", relx=0.5, rely=0.5)

        self.icon_frame.pack(side=tkinter.RIGHT)
        self.icon_label = tkinter.Label(
            self.icon_frame, image=self.icon_image_zoomed, width=320, height=320
        )
        self.icon_label.pack()
        self.update()

    def destroy(self):
        # self.icon_frame.destroy()
        tkinter.BaseWidget.destroy(self)


def main() -> None:
    global ex
    global root
    global conf
    global icon_image
    root = tkinter.Tk()
    root.withdraw()  # don't show client window until everything is drawn and deiconify() is called
    splash = Splash(root)
    icon_image = splash.icon_image
    parser = argparse.ArgumentParser(description="SPOTClient")
    parser.add_argument(
        "config", nargs="?", default="/var/sagax/spotclient/spotclient.toml"
    )
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
    root.iconphoto(False, icon_image)
    root.geometry("1200x850")
    root.wm_title(f"SPOTClient {pysagax.__version__}")
    root.protocol("WM_DELETE_WINDOW", on_close)
    ex = Client(root)
    root.deiconify()
    splash.destroy()
    root.mainloop()


if __name__ == "__main__":
    main()
