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

from pysagax.message.data_pb2 import SoundSignal, WavHeaderInfos
from pysagax.message.data_types import DataType

from pysagax.util.queue_put import queue_put


import multiprocessing as mp

"""TODO list
check live changes if they are needed

compress stream packets using zlib
if I missed the header packet of a wav stream, can I reconstruct it?
    check header info, it doesn't mach previous than also contstruct a new header

TEST:
    I start a stream then pause it and start a new one (that has different headers) will ffmpeg die??
    
poll ffmpeg status
dont even start if I dont have the header packet

"""

def generate_wav_header(length_of_format:int, type_of_format:int, number_of_channels: int, sample_rate:int, bits_per_sample: int):
    """
    Generate the wav header bytes for a continous stream
    file size is set as FFFFFFFF
    """
    bytes_per_sample: int = int(sample_rate * bits_per_sample * number_of_channels / 8) #TODO:  	(Sample Rate * BitsPerSample * Channels) / 8

    block_alignment:int = int(bits_per_sample * number_of_channels / 8) # TODO:  (BitsPerSample * Channels) / 8.1 - 8 bit mono2 - 8 bit stereo/16 bit mono4 - 16 bit stereo 

    header =  b""
    header += b'RIFF'
    header += b'\xFF\xFF\xFF\xFF'  # Place holder for chunk size
    header += b'WAVE'
    header += b'fmt '
    header += length_of_format.to_bytes(length=4, byteorder="little") # Sub chunk size
    header += type_of_format.to_bytes(length=2, byteorder="little") # audio format, always little endian 1
    header += number_of_channels.to_bytes(length=2, byteorder="little") # number of channels, always 1
    header += sample_rate.to_bytes(length=4, byteorder='little') # sample rate
    header += bytes_per_sample.to_bytes(length=4, byteorder='little') # bytes per sample
    header += block_alignment.to_bytes(length=2, byteorder="little") # block alignment
    header += bits_per_sample.to_bytes(length=2, byteorder="little") # bits per sample
    header += b'data'
    header += b'\xFF\xFF\xFF\xFF' # place holder for sub chunk size

    return header

class AudioStreamer(mp.Process):
    """
    Process that has the task of turning wav packets into mp3 udp packets using ffmpeg

    """

    def __init__(
        self, stream_id, wav_header: WavHeaderInfos, in_q: Queue, out_q: Queue, stop_event: mp.Event, level: Any
    ):
        super().__init__()
        self._stream_id = stream_id
        self._wav_header = wav_header
        self._logger = logging.getLogger(f"AudioStreamer#{stream_id:02d}")
        self._logger.setLevel(level)
        self.daemon = True

        self._default_port_start = 4300  # TODO: move to config file

        self._in_q = in_q
        self._out_q = out_q
        self._stop_event = stop_event

        self._ffmpeg_process = None

        self._fifo_path = f"/tmp/audio_pipe_stream_id_{self._stream_id}"
        self._destination_ip = "127.0.0.1"
        self._destination_port = self._default_port_start + self._stream_id

        # packet size: ideally a multiple of 188??
        self._packet_size = 1316  # TODO: move to config or command

        # function for receiving data from ffmpeg
        self._receive_ffmpg_data_fn = None

        self._latest_packet_id = 0  # incremental id for packet order tracking

    def _start_ffmpeg_server(self):
        """ """
        import subprocess

        # TODO: check input and stream options of mmpeg
        transport_format = "mpegts"
        # FFmpeg command: read wav -> encode as mp3 -> send over UDP
        cmd = [
            "ffmpeg",
            "-re",  # read input at native rate (real-time)
            "-i",
            self._fifo_path,  # input fifo
            "-acodec",
            "aac",
            "-b:a",
            "32k",
            # "-c:a", "libopus",
            "-f",
            transport_format,  # transport stream format (easy for VLC)
            f"udp://{self._destination_ip}:{self._destination_port}?pkt_size={self._packet_size}",
        ]

        # Run FFmpeg
        self._logger.info("START ffmpeg")
        self._ffmpeg_process = subprocess.Popen(cmd)
        self._logger.info("STARTED ffmpeg")

    def _setup_fifo(self):
        # Create FIFO if it doesn’t exist
        if not os.path.exists(self._fifo_path):
            self._logger.info(f"Creating FIFO at {self._fifo_path}")
            os.mkfifo(self._fifo_path)
        else:
            # If it exists but isn’t a FIFO, abort
            # if not stat.S_ISFIFO(os.stat(fifo_path).st_mode):
            #     print(f"[ERROR] {fifo_path} exists but is not a FIFO", file=sys.stderr)
            #     sys.exit(1)
            self._logger.critical("CANT CREATE FIFO, AUDIO STREAM MIGHT NOT WORK")
            # TODO: what happens here, is this a problem?
            pass

    def _connect_to_ffmpeg(self):

        # Create UDP socket for incoming stream
        rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx_sock.bind((self._destination_ip, self._destination_port))

        rx_sock.settimeout(0.001)  # 0 timout doesn't really work here for some reason

        def receive_fn():
            # TODO: MPEG-TS packets are ~1316 bytes ????
            data, _ = rx_sock.recvfrom(2048)
            return data

        self._receive_ffmpg_data_fn = receive_fn

    def _send_wav_header_to_ffmpeg(self, fifo):
        header_bytes = generate_wav_header(
            length_of_format=self._wav_header.length_of_format,
            type_of_format=self._wav_header.type_of_format,
            number_of_channels=self._wav_header.number_of_channels,
            sample_rate=self._wav_header.sample_rate,
            bits_per_sample=self._wav_header.bits_per_sample,
        )
        fifo.write(header_bytes)
        fifo.flush()
        self._logger.trace(f"flushed wav header to FIFO: {header_bytes}")



    def _process_sound_signal(self, sound_signal: SoundSignal, fifo):
        wav_chunk = sound_signal.data
        fifo.write(wav_chunk)
        fifo.flush()
        self._logger.trace(f"flushed {sound_signal.packet_id} to FIFO")

    def _collect_udp_packets(self):
        """
        Collect all the udp packets before a timeout (but max 10 at a time)
        TODO: a nicer solution that is flexible so both process_sound_signal and
            collect_udp_packets can run as often as they need to independently of each other
        """
        data_list = []
        while len(data_list) < 10:
            try:
                data_list.append(self._receive_ffmpg_data_fn())
            except TimeoutError:
                break
        return data_list

    def _send_processed_sound_signals(self, udp_packets):
        for data in udp_packets:
            self._logger.trace("Sending UDP audio stream packet")
            out_packet = SoundSignal()
            out_packet.demod_id = self._stream_id
            self._latest_packet_id += 1
            out_packet.packet_id = self._latest_packet_id
            out_packet.data = data

            queue_put(
                self._out_q,
                out_packet,
                timeout=0,
                logger=self._logger,
                message="out queue",
            )

    def _teardown(self):
        self._ffmpeg_process.kill()
        if os.path.exists(self._fifo_path):
            os.remove(self._fifo_path)
            self._logger.info(f" Removed FIFO {self._fifo_path}")

    def run(self):
        # setup
        self._start_ffmpeg_server()
        self._setup_fifo()
        self._connect_to_ffmpeg()

        with open(self._fifo_path, "wb") as fifo:
            self._send_wav_header_to_ffmpeg(fifo)
        
            # loop
            while not self._stop_event.is_set():
                self._loop(fifo)

        # teardown
        self._teardown()

    def _loop(self, fifo):
        # main loop

        # get data chunk from imput queue
        try:
            sound_signal = self._in_q.get(timeout=0.1)
            self._logger.trace("received wav audio packet")
        except queue.Empty:
            sound_signal = None

        if sound_signal is not None:
            self._process_sound_signal(sound_signal, fifo)

        udp_packets = self._collect_udp_packets()

        self._send_processed_sound_signals(udp_packets)


class AudioStreamerHandler:
    def __init__(self, stream_id, wav_header, processed_packets_return_q, level):

        self.wav_header = wav_header

        self._logger = logging.getLogger(f"AudioStreamerHandler#{stream_id:02d}")

        self._stream_id = stream_id
        self._to_audio_streamer_q = mp.Queue()
        self._stop_event = mp.Event()
        self._streamer = AudioStreamer(
            stream_id=stream_id,
            wav_header=self.wav_header, 
            in_q=self._to_audio_streamer_q,
            out_q=processed_packets_return_q,
            stop_event=self._stop_event,
            level=level,
        )

        self._latest_push = time.time()

    def process_data(self, data: SoundSignal):
        self._latest_push = time.time()
        queue_put(self._to_audio_streamer_q, data, timeout=0, logger=self._logger)

    def start(self):
        self._streamer.start()

    def stop(self):
        self._logger.debug(f"Stopping AudioStreamer#{self._stream_id}")
        self._stop_event.set()

    def join(self):
        self._logger.debug("Waiting for AudioStreamer to join...")
        self._streamer.join()
        self._logger.debug("AudioStreamer connection joined!")

    def is_old(self):
        """If the streamer has not been used for 15 secs it is deemed old and can be stopped"""
        age = time.time() - self._latest_push
        return age > 15


class AudioStreamProcessor(Loop):
    """Background process for converting the incoming wav audio stream to a compressed stream of encoded udp packets using ffmpeg"""

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        self._in_queue: Optional[Queue] = None
        self._out_queue: Optional[Queue] = None

        # stream_id -> AudioStreamerHandler
        self._active_streams: dict[int, AudioStreamerHandler] = {}

    def __call__(
        self,
        in_queue: Queue[list[SoundSignal]],
        out_queue: Queue[list[SoundSignal]],
        *args,
        **kwargs,
    ) -> None:
        self._in_queue = in_queue
        self._out_queue = out_queue
        return super()._call(*args, **kwargs)

    # self._create_new_stream()

    def _start_audio_streamer(self, stream_id, wav_header):
        sh = AudioStreamerHandler(stream_id, wav_header, self._out_queue, level=self._logger.level)
        self._active_streams[stream_id] = sh
        sh.start()

        self._logger.info(f"Activated AudioStreamer#{stream_id} )")

    def _handle_incoming_sound_signal(self, sound_signal: SoundSignal):
        stream_id = sound_signal.demod_id
        if stream_id not in self._active_streams.keys():
            # start audio stream if it doesn't exist
            self._start_audio_streamer(stream_id, sound_signal.wav_header)
        
        if self._active_streams[stream_id].wav_header != sound_signal.wav_header:
            # Restart audio stream if wav header changed
            self._active_streams[stream_id].stop()
            self._active_streams[stream_id].join()
            del self._active_streams[stream_id]
            self._start_audio_streamer(stream_id, sound_signal.wav_header)            

        self._active_streams[stream_id].process_data(sound_signal)

    def _shut_down_old_streamers(self):
        to_remove_ids = []
        for id, sh in self._active_streams.items():
            if sh.is_old():
                self._logger.info(f"Trying to deactivate AudioStreamer#{id} )")
                sh.stop()
                sh.join()
                to_remove_ids.append(id)

        for id in to_remove_ids:
            del self._active_streams[id]
            self._logger.info(f"Deactivated AudioStreamer#{id} )")

    def _loop(self) -> None:

        self._shut_down_old_streamers()

        # get incoming data
        try:
            in_packet = self._in_queue.get(timeout=0.1)
            self._logger.trace(f"Received audio packet")
        except queue.Empty:
            return

        # handle in_packet contents one-by-one
        for sound_signal in in_packet:
            self._handle_incoming_sound_signal(sound_signal)

        # the AudioStreamer instances automatically sends the generated udp packet to PPStreamPrep
