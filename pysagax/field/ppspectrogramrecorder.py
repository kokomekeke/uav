from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue
from time import sleep
from datetime import datetime
import os

from typing import Any, Optional, Literal

import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading
from pysagax.message.proto_stream_to_file import FileStreamer
from pysagax.util.protobuf_spectrum_utils import cast_all_spectrums_in_measurement
from pysagax.util.queue_put import queue_put

from pysagax.common.loop import Loop
from enum import Enum

Mode = Enum("Mode", ["PASS", "RECORD", "PLAYBACK"])


class PPSpectrogramRecorder(Loop):
    """
    Background process for recording/replaying Measurement stream.

    Currently it can be configured from CLI or config file.


    mode:
        PASS: incoming packets are pushed without saving to file.
        RECORD: incoming packets are pushed and saved to a file
        PLAYBACK: pushed packets are read from a file.

    path: the path of the recording file that is to be recorded or played back.
        The path is extended with the current timestamp for recordings.

    recording_dtype: useful for reducing recording file sizes
        ORIGINAL: keep the original data type for the recordings
        INT8, INT16, FLOAT16, FLOAT32: cast the spectrum data to one of these datatypes before saving to file.
    """

    def __init__(
        self,
        mode: str,
        path: str,
        recording_dtype: Optional[
            Literal["ORIGINAL", "INT8", "INT16", "FLOAT16", "FLOAT32"]
        ] = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self.recording_dtype: Optional[proto_data.Spectrum.DataType.ValueType] = None
        if recording_dtype is not None and recording_dtype.upper() != "ORIGINAL":
            self.recording_dtype = proto_data.Spectrum.DataType.Value(
                recording_dtype.upper()
            )
            self._logger.info(
                f"Spectrogram recording will use {proto_data.Spectrum.DataType.Name(self.recording_dtype)} data type."
            )
        else:
            self.recording_dtype = None

        self.mode = Mode[mode.upper()]
        self.path = path
        self._logger.info(
            f"Initialized with mode='{self.mode.name}' and path='{path}'."
        )

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
        except queue.Empty:
            return
        self._change_mode(new_path, new_mode)

    def _change_mode(self, new_path: str, new_mode: Mode):
        if new_mode == self.mode and self.path == new_path:
            # no state change
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
                # Inserting a timestamp before the file extension
                start_time_string = datetime.now().strftime("%Y%m%d_%H%M%S")
                name, extension = os.path.splitext(new_path)
                new_path = f"{name}_{start_time_string}{extension}"

                self._file_streamer = FileStreamer(path=new_path, mode="record")
            case Mode.PLAYBACK:
                self._file_streamer = FileStreamer(path=new_path, mode="playback")
        self.mode = new_mode
        self.path = new_path

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
        queue_put(self._queue_out, packet, timeout=0.1, logger=self._logger)

        # pushing measurement packet
        if self.mode == Mode.RECORD:
            if self.recording_dtype is not None:
                cast_all_spectrums_in_measurement(
                    packet, self.recording_dtype, inplace=True
                )
            self._file_streamer.put(packet)

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
