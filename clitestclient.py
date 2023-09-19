#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 08/09/2023.
#
from __future__ import annotations

import argparse
import multiprocessing
import queue
import threading
from datetime import datetime
from time import sleep
from typing import Optional

from pysagax import StreamAndCompassProcess
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
        BaseConnection.__init__(self)
        threading.Thread.__init__(self)

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

    def status_watcher_thread(self, status_queue: queue.Queue[str]) -> None:
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
                    else:
                        print(f"[Stream] {message}")
                self.disconnect_value.value = self.disconnect
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

        # The purpose of the watcher thread is to take the status messages from the multiprocessing process and display
        # them on the GUI, and to forward the disconnect signal to the process if the "Disconnect" button is clicked.
        watcher_thread = threading.Thread(
            target=self.status_watcher_thread,
            args=[status_queue],
            daemon=True,
        )
        watcher_thread.start()

        packets_queue: multiprocessing.Queue[
            tuple[float, CoreServicePacket]
        ] = multiprocessing.Queue()
        """
        This queue will transfer the processed packets from the stream process to the main (GUI) process
        """

        stream_process = StreamAndCompassProcess(
            [packets_queue], self.disconnect_value, status_queue
        )

        stream_process.host_port = self.host_port
        stream_process.start()

        # The code below will handle the preprocessed packets from the stream process
        while True:
            if self.disconnect or not watcher_thread.is_alive():
                break
            try:
                angle, packet = packets_queue.get(
                    timeout=0.5
                )  # get a packet from the stream process
            except queue.Empty:
                continue
            ts = datetime.fromtimestamp(packet.time_ns / 1e9, tz=None)
            print(
                f"[{packet.stream_id}] {ts.strftime('%H:%M:%S')}.{int((packet.time_ns % 1e9) / 1e6):03d} - "
                f"{str(packet)} - {angle}",
            )
        self.disconnect_value.value = True
        stream_process.join()
        stream_process.terminate()


class CsClient:
    def __init__(self) -> None:
        global args
        self.command_thread = CommandsConnectionThread()
        self.stream_thread = TestStreamDisplayThread()

        self.command_thread.connect_action = self.command_connect_action
        self.command_thread.disconnect_action = self.command_disconnect_action
        self.command_thread.host_port = f"{args.address}:12936"
        self.command_thread.start()
        self.stream_thread.host_port = f"{args.address}:12937"
        self.stream_thread.start()

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

    def disconnect_all(self) -> None:
        """
        Action of the "Disconnect" button
        """
        self.command_thread.disconnect = True
        self.stream_thread.disconnect = True

    def command_connect_action(self) -> None:
        print("## Command Connected")

    def command_disconnect_action(self) -> None:
        print("## Command Disconnected")
        self.disconnect_all()


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    client = CsClient()
    while client.command_thread.is_alive() and client.stream_thread.is_alive():
        inp = input()
        if not inp:
            break
        client.send_command(inp)
    client.disconnect_all()
