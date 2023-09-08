#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 08/09/2023.
#
from __future__ import annotations

import argparse
import math
import multiprocessing
import os
import queue
import struct
import threading
import time
import typing
from datetime import datetime
from time import sleep
from typing import Any, Callable, Optional

import numpy as np
import numpy.typing as npt

from pysagax.lena_core_service import (
    BaseConnection,
    CoreServicePacket,
    StreamConnectionProcess,
)

parser = argparse.ArgumentParser(description="CLI Test client parameters")
parser.add_argument("address")
args = parser.parse_args()


class CommandsConnectionThread(BaseConnection, threading.Thread):
    def __init__(self) -> None:
        super(CommandsConnectionThread, self).__init__()

    def receive_on_socket(self, data: bytes) -> None:
        """
        When text is received on the command socket, display it in the console textbox.
        """
        print(f"# {data.decode()}")

    def display_status(self, message: str) -> None:
        pass

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.disconnect = False
        self.run_socket()


"""
This thread is responsible for handling the multiprocessing stream process and for displaying the stream contents
on the matplotlib plots
"""


class TestStreamDisplayThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__()
        self.roi_packet: Optional[CoreServicePacket] = None
        """
        Latest ROI packet
        """

        self.roi_bin: int = 0
        """
        FFT bin position of ROI result
        """

        self.disconnect: bool = False
        """
        When the disconnect flag is set, the thread loop will quit on the next iteration.
        """

        self.host_port = ""
        """
        Host and port in <address>:<tcp port> format.
        """

        self.notification_message = ""
        """
        Last notification message from the stream port
        """

        manager = multiprocessing.get_context("spawn").Manager()
        self.disconnect_value = manager.Value("i", 0)
        """
        Setting the '1' value of the disconnect_value multiprocessing variable will end the multiprocessing task on the
        next iteration.
        """

    def status_watcher_thread(
        self, status_queue: queue.Queue[str], packet_string_queue: queue.Queue[str]
    ) -> None:
        """
        Entry point of the watcher thread
        """
        while True:
            try:
                terminate = False
                while not status_queue.empty():
                    message = status_queue.get(
                        timeout=0.2
                    )  # get status message from stream process
                    if message == "END":
                        terminate = True
                    print(message)
                self.disconnect_value.value = self.disconnect
                while not packet_string_queue.empty():
                    print(packet_string_queue.get())
                if terminate:
                    return
            except queue.Empty:
                pass
            except BrokenPipeError:
                return
            except RuntimeError:
                return  # it might happen on the UI when closing the window

    def run(self) -> None:
        """
        Entry point of the data handling thread
        """

        global args
        status_queue: multiprocessing.Queue[str] = multiprocessing.Queue()
        """
        The string elements of the status queue are the messages to be displayed on the GUI status bar
        """

        packet_string_queue: queue.Queue[str] = queue.Queue()

        # The purpose of the watcher thread is to take the status messages from the multiprocessing process and display
        # them on the GUI, and to forward the disconnect signal to the process if the "Disconnect" button is clicked.
        watcher_thread = threading.Thread(
            target=self.status_watcher_thread,
            args=(status_queue, packet_string_queue),
            daemon=True,
        )
        watcher_thread.start()

        packets_queue: multiprocessing.Queue[
            CoreServicePacket
        ] = multiprocessing.Queue()
        """
        This queue will transfer the processed packets from the stream process to the main (GUI) process
        """

        stream_process = StreamConnectionProcess(
            packets_queue, self.disconnect_value, status_queue
        )

        stream_process.host_port = self.host_port
        stream_process.start()

        # The code below will handle the preprocessed packets from the stream process
        while True:
            if self.disconnect:
                break
            try:
                packet: CoreServicePacket = packets_queue.get(
                    timeout=0.5
                )  # get a packet from the stream process
            except queue.Empty:
                continue
            ts = datetime.fromtimestamp(packet.time_ns / 1e9, tz=None)
            packet_string_queue.put(
                f"[{packet.stream_id}] {ts.strftime('%H:%M:%S')}.{int((packet.time_ns % 1e9) / 1e6):03d} - "
                f"{str(packet)}",
            )  # handle UI in a separate thread, because UI calls are slow

        stream_process.join()
        stream_process.terminate()


class CsClient:
    def send_command(self, cmd: str) -> None:
        """
        Send the command from the command entry box to the client. Called on pressing the Return key in the autocomplete box.
        """
        assert self.command_thread
        assert self.command_thread.client_socket
        cmd = cmd.replace("\n", "").replace("\r", "")
        for cmd_line in cmd.split(";"):  # One command per line
            if not cmd_line:
                continue
            cmd_line = cmd_line.strip()
            cmd_line += ";"
            self.command_thread.client_socket.send(cmd_line.encode())
            sleep(0.1)

    def connect_commands(self) -> None:
        """
        Action of the "Connect" button
        """
        global args
        self.command_thread = CommandsConnectionThread()
        self.command_thread.connect_action = self.connect_action
        self.command_thread.disconnect_action = self.disconnect_action
        self.command_thread.host_port = f"{args.address}:12936"
        self.command_thread.start()
        self.stream_thread = TestStreamDisplayThread()
        self.stream_thread.host_port = f"{args.address}:12937"
        self.stream_thread.start()

    def disconnect_commands(self) -> None:
        """
        Action of the "Disconnect" button
        """
        if self.command_thread is not None:
            self.command_thread.disconnect = True
        if self.stream_thread is not None:
            self.stream_thread.disconnect = True
            if self.stream_thread.disconnect_value is not None:
                self.stream_thread.disconnect_value.value = True

    def connect_action(self) -> None:
        print("## Command Connected")

    def disconnect_action(self) -> None:
        print("## Command Disconnected")


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    ex = CsClient()
    ex.connect_commands()
    while True:
        inp = input()
        if not inp:
            break
        ex.send_command(inp)
    ex.disconnect_commands()
