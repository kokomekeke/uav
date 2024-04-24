from __future__ import annotations

from pysagax.communication.req_rep_tcp import REQ
import threading
import pysagax.message.command_pb2 as proto_cmd
import time
from typing import Callable, Iterable, Optional, Any


import multiprocessing
import queue


class CommandThread(threading.Thread):
    def __init__(
        self,
        connection: REQ,
        thread_status_queue: queue.Queue[str] | multiprocessing.Queue[str] | None,
        connection_status_queue: queue.Queue[str] | multiprocessing.Queue[str] | None,
    ) -> None:
        super().__init__(daemon=True, name="CommandThread")
        self._connection = connection
        self._thread_status_queue = thread_status_queue
        self._connection_status_queue = connection_status_queue

        # This function handle is called when the socket is initiating connection.
        self.connect_callback: Optional[Callable[[], None]] = None

        # This function handle is called when the socket is initiating connection.
        self.connected_callback: Optional[Callable[[], None]] = None

        # This function handle is called when the socket is disconnected.
        self.disconnect_callback: Optional[Callable[[], None]] = None

        self.command_id = 1

        self.do_disconnect: bool = False

        # timestamp for last received message:
        self._last_heartbeat_time: int = 0
        # connection deemed broken if nothing is received for this much time:
        self.heartbeat_timeout_ns: int = 10e9
        # last outgoing request timestamp:
        self._last_command_time: int = 0

        self._command_queue: queue.Queue = queue.Queue()
        self._do_abort: bool = False
        self._response_handlers: dict[Any, Callable[[Any], None]] = {}

    def enqueue_commands(self, commands: list) -> None:
        self._do_abort = False
        if not isinstance(commands, list):
            commands = [commands]
        for cmd in commands:
            cmd.id = self.command_id % 2**31  # staying in the range of int32
            self.command_id += 1
            self._command_queue.put(cmd)
            # if cmd not in self.command_queue.queue:
            #     self.command_queue.put(cmd)

    def abort_commands(self) -> None:
        self._do_abort = True
        while not self._command_queue.empty():
            self._command_queue.get()  # clear queue
        self._display_thread_status_callback(False, "")

    def _connect(self) -> bool:
        self._display_connection_status_callback("Connecting...")
        if self.connect_callback is not None:
            self.connect_callback()
        connected = self._connection.connect()

        # TODO: REP.connect() always retuns True
        if not connected:
            self.disconnect_callback()  # disconnect callback?
            self.display_connection_status_callback("Connection failed")
            return False

        if self.connected_callback is not None:
            self.connected_callback()
        self._last_heartbeat_time = time.time_ns()
        self._display_connection_status_callback("Connected")
        return True

    def _disconnect(self):
        self.disconnect_callback()

    def _is_disconnect(self) -> bool:
        if self.do_disconnect:
            self._display_connection_status_callback("Disconnected")
            return True
        if time.time_ns() - self._last_heartbeat_time > self.heartbeat_timeout_ns:
            self._display_connection_status_callback("Disconnected (timeout)")
            return True
        return False

    def run(self) -> None:
        if not self._connect():
            return
        self._loop()
        self._disconnect()

    def _loop(self):
        while not self._is_disconnect():
            if self._do_abort:
                continue
            command = self._get_next_command()
            if command is None:
                time.sleep(0.1)
                continue
            # print("COMMAND:\n", command)  ####
            raw_response = self._connection.send(
                command.SerializeToString(), timeout=2000
            )
            if raw_response is None:
                self._timeout_handler(command)
                continue
            self._last_heartbeat_time = time.time_ns()
            response = proto_cmd.Response()
            response.ParseFromString(raw_response)
            if response.error.description:  # TODO: rethink error handling
                print(
                    f"\n#############\nERROR IN '{proto_cmd.Instruction.Name(command.instruction)}' COMMAND RESPONSE: {response.error.description}"
                    f"\n#############\n"
                )
                if response.instruction != proto_cmd.CONFIG_STATUS:
                    cmd = proto_cmd.Command(instruction=proto_cmd.CONFIG_STATUS)
                    self.enqueue_commands(cmd)
                # TODO: dont run response handlers if error in response,
                #      OR make response handlers that check the error field
                continue  # skipping response handler

            # print("RESPONSE:\n", response, "\n================\n")  ####
            try:
                self._response_handler(response)
            except Exception as e:
                print(
                    f"ERROR in command response handler: \n COMMAND: {command} \n RESPONSE: {response}"
                )
                raise e
        self._display_thread_status_callback(False, "")

    def _get_next_command(self):
        if self._command_queue.empty():
            if time.time_ns() - self._last_command_time > self.heartbeat_timeout_ns / 2:
                # send PING if no communication for a long time
                self.ping("heartbeat")
            else:
                self._display_thread_status_callback(False, "")
                return None
        command = self._command_queue.get(block=True, timeout=1)
        self._display_thread_status_callback(True, command)
        self._last_command_time = time.time_ns()
        return command

    def ping(self, ping_data: str = "ping"):
        ping_cmd = proto_cmd.Command()
        ping_cmd.instruction = proto_cmd.PING
        ping_cmd.ping_data = ping_data
        self.enqueue_commands(ping_cmd)

    def set_response_handler(
        self, command_instruction, handler: Callable[[Any], None]
    ) -> None:
        """
        Adds or replaces the response handler callback function for a specific command
        :param command: the command to set the response handler for (without semicolon)
        :param handler: callback function (command: str, response: list[str])
        :return:
        """
        # use command instructions as handles?
        self._response_handlers[command_instruction] = handler

    def _response_handler(self, response) -> None:

        for key, handler in self._response_handlers.items():
            if key == response.instruction:
                handler(response)
        pass

    def _timeout_handler(self, command) -> None:
        self._display_connection_status_callback(
            f"Command {proto_cmd.Instruction.Name(command.instruction)} timed out."
        )

    def _display_connection_status_callback(self, message: str) -> None:
        """
        Is called by the base class to display the status of the TCP socket on the GUI.
        :param message: text to display on the GUI
        :return:
        """
        if self._connection_status_queue is not None:
            self._connection_status_queue.put(message)

    def _display_thread_status_callback(self, working: bool, command) -> None:
        if self._thread_status_queue is not None:
            self._thread_status_queue.put([working, str(command)])
            # TODO: put the actual commands in the queue (it gives error now)
