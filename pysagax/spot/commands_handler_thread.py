from __future__ import annotations

import multiprocessing
import queue
import shlex
import threading
import time
from typing import Callable

from pysagax.spot.commands_connection_thread import CommandsConnectionThread


class CommandsHandlerThread(threading.Thread):
    """
    Asynchronous handling of the CoreService command queue
    """
    def __init__(
        self,
        conn: CommandsConnectionThread,
        status_callback: Callable[[bool, str], None],
        status_queue: queue.Queue[str] | multiprocessing.Queue[str],
    ):
        super().__init__(daemon=True)
        self.conn = conn
        self.command_queue: queue.Queue[str] = queue.Queue()
        self.do_abort: bool = False
        self.status_callback = status_callback
        """
        Callback to display status of commands
        bool: is working on a command
        str: the command it is working on
        """
        self.status_queue = status_queue
        self.response_handlers: dict[str, Callable[[str, list[str]], None]] = {}

    def set_response_handler(
        self, command: str, handler: Callable[[str, list[str]], None]
    ) -> None:
        """
        Adds or replaces the response handler callback function for a specific command
        :param command: the command to set the response handler for (without semicolon)
        :param handler: callback function (command: str, response: list[str])
        :return:
        """
        self.response_handlers[command] = handler

    def run(self) -> None:
        while not self.conn.connected:
            time.sleep(0.1)
            if self.conn.disconnect:
                return
        while self.conn.connected:
            if not self.command_queue.empty():
                while (
                    (not self.command_queue.empty())
                    and not self.do_abort
                    and self.conn.connected
                ):
                    command = self.command_queue.get(block=True, timeout=1)
                    self.status_callback(True, command)
                    response = self.conn.send_command(command)
                    if response is None:
                        self._timeout_handler(command)
                    else:
                        try:
                            self._response_handler(command, response)
                        except Exception as e:
                            print(
                                f"ERROR in command response handler: \n COMMAND: {command} \n RESPONSE: {response}"
                            )
                            # traceback.print_exception(type(e), e, e.__traceback__)
                            raise e

                self.status_queue.put("#action" + "send_commands_finished")
                self.status_callback(False, "")
            time.sleep(0.1)

    def _timeout_handler(self, command: str) -> None:
        self.status_queue.put(f"Command {command} timed out.")

    def _response_handler(self, command: str, response: str) -> None:
        response_parts = shlex.split(response)  # response.split(" ")
        error_code = int(response_parts[0])
        for key, handler in self.response_handlers.items():
            if key in command:
                handler(command, response_parts)
        if error_code:
            self.status_queue.put(f'#infoError with command "{command}": {response}')

    def enqueue_commands(self, commands: str) -> None:
        self.do_abort = False
        cmd = commands.replace("\n", "").replace("\r", "")
        for cmd_line in cmd.split(";"):  # One command per line
            if not cmd_line:
                continue
            cmd_line = cmd_line.strip()
            cmd_line += ";"
            if cmd_line not in self.command_queue.queue:
                self.command_queue.put(cmd_line)

    def abort_commands(self) -> None:
        self.do_abort = True
        while not self.command_queue.empty():
            self.command_queue.get()  # clear queue
        self.status_callback(False, "")
