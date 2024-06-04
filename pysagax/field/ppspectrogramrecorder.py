from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue
from time import sleep

from typing import Any, Optional

import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading
from pysagax.message.proto_stream_to_file import FileStreamer

from pysagax.common.loop import Loop
from enum import Enum

# class Mode(Enum):
Mode = Enum("Mode", ["PASS", "RECORD", "PLAYBACK"])


class PPSpectrogramRecorder(Loop):
    """
    Background process for recording/replaying Measurement stream.
    """

    def __init__(self, 
        mode: str,
        path: str,
        *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None

        self.mode = Mode[mode.upper()]
        self.path = path
        #TODO: in recording mode use timestamped file names i guess
        self._logger.info(f"Initialized with mode='{self.mode.name}' and path='{path}'.")

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out
        self._enter_new_mode(self.path, self.mode)
        return super()._call(*args, **kwargs)

    def _read_commands(self):
        """Gets commands and handles state transitions"""
        try:
            # TODO new_path, new_mode  = command_queue.get_nowait
            new_mode = self.mode
            new_path = self.path
            pass
        except queue.Empty:
            return
        self._change_mode(new_path, new_mode)

    def _change_mode(self, new_path: str, new_mode: Mode):
        if new_mode == self.mode and self.path == new_path:
            # no state change
            # TODO: use self._file_streamer.path() ??
            return
        self._exit_current_mode()
        self._enter_new_mode(new_path, new_mode)

    def _exit_current_mode(self):
        # Exiting current state:
        match self.mode:
            case Mode.PASS:
                pass
            case Mode.RECORD:
                self._file_streamer.close()
                self._file_streamer = None
            case Mode.PLAYBACK:
                self._file_streamer.close()
                self._file_streamer = None

    def _enter_new_mode(self, new_path, new_mode):
        # Entering new state:
        match new_mode:
            case Mode.PASS:
                pass
            case Mode.RECORD:
                self._file_streamer = FileStreamer(path=new_path, mode="record")
            case Mode.PLAYBACK:
                self._file_streamer = FileStreamer(path=new_path, mode="playback")
        self.mode = new_mode

    def _get_packet(self, timeout=1) -> proto_data.Measurement:
        # reading measurement packet
        if self.mode in [Mode.PASS, Mode.RECORD]:
            packet = self._queue_in.get(block=True, timeout=timeout)
        elif self.mode in [Mode.PLAYBACK]:
            packet = self._file_streamer.get(timeout)
        else:
            raise Exception("Undefined mode")
        return packet

    def _put_packet(self, packet):
        # pushing measurement packet
        if self.mode == Mode.RECORD:
            self._file_streamer.put(packet)

        self._queue_out.put(packet)
        self._logger.debug(f"Record/Playback finished on packet {packet.packet_id}")

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None

        self._read_commands()
        try:
            packet = self._get_packet(timeout=1)

            assert isinstance(packet, proto_data.Measurement)

            self._put_packet(packet)
        except queue.Empty:
            pass
