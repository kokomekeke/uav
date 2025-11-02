from __future__ import annotations
import logging
import queue
from queue import Queue
import time


import os
import sys
from typing import Optional

import socket

from pysagax.common.loop import Loop

from pysagax.message.data_pb2 import SoundSignal
from pysagax.message.data_types import DataType

from pysagax.util.queue_put import queue_put


class AudioRetransmitter:
    def __init__(self, ip, port):
        self._ip = ip
        self._port = port

        self._tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def transmit(self, packet: SoundSignal):
        data = packet.data
        self._tx_sock.sendto(data, (self._ip, self._port))


class AudioStreamer(Loop):
    """Retransmits the UDP stream packets"""

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        self._in_queue: Optional[Queue] = None

        # stream_id -> AudioRetransmitter
        self._active_streamers: dict[int, AudioRetransmitter] = {}

        self._ip = "127.0.0.1"

        self._default_port_start = 4400  # TODO: move to config file

    def __call__(
        self,
        in_queue: Queue[list[SoundSignal]],
        *args,
        **kwargs,
    ) -> None:
        self._in_queue = in_queue
        return super()._call(*args, **kwargs)

    def _start_retransmitter(self, stream_id):
        port = self._default_port_start + stream_id
        ar = AudioRetransmitter(self._ip, port)
        self._active_streamers[stream_id] = ar
        self._logger.info(
            f"\n\n"
            f"\t\t##############################################\n"
            f"\t\t#   Audio stream started on {self._ip}:{port}   #\n"
            f"\t\t##############################################\n"
        )

    def _handle_incoming_sound_signal(self, sound_signal: SoundSignal):
        stream_id = sound_signal.demod_id
        if stream_id not in self._active_streamers.keys():
            self._start_retransmitter(stream_id)

        self._active_streamers[stream_id].transmit(sound_signal)

    def _loop(self) -> None:

        # get incoming data
        try:
            in_packet = self._in_queue.get(timeout=0.1)
            self._logger.trace(f"Audio data received")
        except queue.Empty:
            return

        # handle in_packet contents one-by-one
        for sound_signal in in_packet:
            self._handle_incoming_sound_signal(sound_signal)
