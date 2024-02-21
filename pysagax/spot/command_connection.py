from __future__ import annotations

from pysagax.communication.req_rep import REQ
import threading
import pysagax.message.command_pb2 as proto
import time
from typing import Callable, Iterable, Optional, Any


import multiprocessing
import queue


class CommandConnection(REQ):
    pass


class CommandThread(threading.Thread):
    def __init__(
        self,
        connection: REQ,
        thread_status_queue: queue.Queue[str] | multiprocessing.Queue[str] | None,
        connection_status_queue: queue.Queue[str] | multiprocessing.Queue[str] | None,
    ) -> None:
        super().__init__(daemon=True, name="CommandThread")
        self.connection = connection
        self.thread_status_queue = thread_status_queue
        self.connection_status_queue = connection_status_queue

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
        self.heartbeat_timeout_ns: int = 60e9
        # last outgoing request timestamp:
        self._last_command_time: int = 0

        self.command_queue: queue.Queue = queue.Queue()
        self.do_abort: bool = False
        self.response_handlers: dict[Any, Callable[[Any], None]] = {}

    def enqueue_commands(self, commands: list) -> None:
        self.do_abort = False
        if not isinstance(commands, list):
            commands = [commands]
        for cmd in commands:
            cmd.id = self.command_id
            self.command_id += 1
            self.command_queue.put(cmd)
            # if cmd not in self.command_queue.queue:
            #     self.command_queue.put(cmd)

    def abort_commands(self) -> None:
        self.do_abort = True
        while not self.command_queue.empty():
            self.command_queue.get()  # clear queue
        self._display_thread_status_callback(False, "")

    def connect(self) -> bool:
        self._display_connection_status_callback("Connecting...")
        if self.connect_callback is not None:
            self.connect_callback()
        connected = self.connection.connect()

        # TODO?: adding client_ddress to connection is necessary to monitor connected status
        # TODO: pysagaxUAV only returns true for the first connection,
        #        and for 10 seconds after launching. (because of REP._init())
        #        We don't check for success until it's fixed
        # if not connected:
        #    self.disconnect_callback() #disconnect callback?
        #    self.display_connection_status_callback("Connection failed")
        #    return False

        if self.connected_callback is not None:
            self.connected_callback()
        self._last_heartbeat_time = time.time_ns()
        self._display_connection_status_callback("Connected")
        return True

    def disconnect(self):
        self.disconnect_callback()

    def is_disconnect(self) -> bool:
        if self.do_disconnect:
            self._display_connection_status_callback("Disconnected")
            return True
        if time.time_ns() - self._last_heartbeat_time > self.heartbeat_timeout_ns:
            self._display_connection_status_callback("Disconnected (timeout)")
            return True
        return False

    def run(self) -> None:
        if not self.connect():
            return
        self.loop()
        self.disconnect()

    def loop(self):
        while not self.is_disconnect():
            if self.do_abort:
                continue
            command = self._get_next_command()
            if command is None:
                time.sleep(0.1)
                continue
            print("COMMAND:\n", command)  ####
            raw_response = self.connection.send(
                command.SerializeToString(), timeout=30000
            )
            self._last_heartbeat_time = time.time_ns()
            if raw_response is None:
                self._timeout_handler(command)
                continue
            response = proto.Response()
            response.ParseFromString(raw_response)
            if response.error.description:
                print(
                    f"\n#############\nERROR IN COMMAND RESPONSE: {response.error.description}"
                    f"\n#############\n"
                )
                # raise Exception(f"Error in command response: {response.error.description}")
            print("RESPONSE:\n", response, "\n================\n")  ####
            try:
                self._response_handler(response)
            except Exception as e:
                print(
                    f"ERROR in command response handler: \n COMMAND: {command} \n RESPONSE: {response}"
                )
                raise e
        self._display_thread_status_callback(False, "")

    def _get_next_command(self):
        if self.command_queue.empty():
            if time.time_ns() - self._last_command_time > self.heartbeat_timeout_ns / 2:
                # send PING if no communication for a long time
                self.ping("heartbeat")
            else:
                self._display_thread_status_callback(False, "")
                return None
        command = self.command_queue.get(block=True, timeout=1)
        self._display_thread_status_callback(True, command)
        self._last_command_time = time.time_ns()
        return command

    def ping(self, ping_data: str = "ping"):
        ping_cmd = proto.Command()
        ping_cmd.instruction = proto.PING
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
        self.response_handlers[command_instruction] = handler

    def _response_handler(self, response) -> None:

        for key, handler in self.response_handlers.items():
            if key == response.instruction:
                handler(response)
        pass

    def _timeout_handler(self, command) -> None:
        self._display_connection_status_callback(
            f"Command {command.instruction} timed out."
        )

    def _display_connection_status_callback(self, message: str) -> None:
        """
        Is called by the base class to display the status of the TCP socket on the GUI.
        :param message: text to display on the GUI
        :return:
        """
        if self.connection_status_queue is not None:
            self.connection_status_queue.put(message)

    def _display_thread_status_callback(self, working: bool, command) -> None:
        if self.thread_status_queue is not None:
            self.thread_status_queue.put([working, str(command)])
            # TODO: put the actual commands in the queue (it gives error now)
