"""A read/write library for length-delimited protobuf messages



BASED ON: https://pypi.org/project/delimited-protobuf/"""

from __future__ import absolute_import

from typing import BinaryIO, Literal, Optional, Type, TypeAlias, TypeVar

from google.protobuf.internal.decoder import _DecodeVarint
from google.protobuf.internal.encoder import _EncodeVarint
from google.protobuf.message import Message
from time import time, sleep
import struct
from queue import Empty
from datetime import datetime
import os

from pysagax.message.data_types import DataType

FileStreamMode: TypeAlias = Literal["record", "playback"]


def modify_recording_path(original_path: str, mode: str) -> str:
    """
    This function can be used to create the recording path in PPSpectrogramRecorder and PPDetectionRecorder.

    It changes the original path to include
    a daily subfolder and current timestamp, and the scanengine mode as well.

    If the folder doesn't exist, it creates it.

    Example (on 2025-05-30, 12:52:47):
    >>> modifiy_recorind_path("/var/sagax/recordings/test.protorec", "MANUAL")
    >>> "/var/sagax/recordings/test_20250530/test_20250530_125247_MANUAL.protorec"
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")

    dir_path, original_file = os.path.split(original_path)
    file_name, ext = os.path.splitext(original_file)

    # Construct new directory path
    new_dir = f"{file_name}_{date_str}"
    new_dir_path = os.path.join(dir_path, new_dir)

    # Try to create the directory if it doesn't exist
    try:
        os.makedirs(new_dir_path, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"Failed to create directory '{new_dir_path}': {e}")

    new_file_name = f"{file_name}_{date_str}_{time_str}_{mode}{ext}"
    modified_path = os.path.join(new_dir_path, new_file_name)

    return modified_path


class FileStreamer:
    """
    Class that makes it possible for protobuf message streams to be recorded to or read back from files.

    Initialization:
        path: path of the recording file.
        mode: either playback or record.

    Modes:
        Record: appends protobuf packets recieved through the put() method to the opened file
        Playback: the get() method returns the next packet from the file with the same amount of delay that the packet was saved to file.
            If no packet is available before the timeout runs out, a queue.Empty is raised.
            the read_all() method returns a list of all the protobuf packets cointained in the file.

    The structure of the saved files are detailed in the docstring for _read()
    """

    def __init__(self, path: str, mode: FileStreamMode) -> None:
        self.path = path
        self.mode = mode

        # TODO check for path, maybe create file if doesn't exist. Overwrite or append to existing file?
        if self.mode == "record":
            self.file_io = open(self.path, "w+b")
        elif self.mode == "playback":
            self.file_io = open(self.path, "rb")
        else:
            raise Exception(f"Undefined FileStreamMode '{self.mode}'")

        # for playback timing. The difference of the first packet's read time and save time
        self._stream_delay: Optional[float] = None

        self._packet_buffer: Optional[Message] = None
        self._ts_buffer: Optional[float] = None

    def get(self, timeout: float = 1) -> Message:
        """
        Returns packets from the protobuf file recording with the same speed as they were saved.
        Throws queue.Empty if no packet can be returned before timeout expires.
        """
        if self.mode != "playback":
            raise Exception(f"Can't use get() in {self.mode} mode")
        current_ts = time()

        if self._packet_buffer is None:
            # buffer empty -> get new packet from file
            packet_ts, packet = self._read()
        else:
            # buffer not empty -> get packet from there
            packet_ts, packet = self._ts_buffer, self._packet_buffer
            self._ts_buffer, self._packet_buffer = None, None

        if packet is None:
            # packet is None -> EOF reached -> wait until timeout and raise queue.Empty
            sleep(timeout)
            raise Empty

        if self._stream_delay is None:
            # if its the first read, we set the correct delay
            self._stream_delay = current_ts - packet_ts

        # packet should be pushed at this timestamp:
        playback_ts = packet_ts + self._stream_delay
        # timeout should happen at this timestamp:
        timeout_ts = current_ts + timeout

        if timeout_ts < playback_ts:
            # timeout -> wait until it's passed, save packets to buffer and raise queue.Empty
            sleep(timeout_ts - current_ts)
            self._ts_buffer, self._packet_buffer = packet_ts, packet
            raise Empty

        if playback_ts > current_ts:
            # wait until it's time to push the packet
            sleep(playback_ts - current_ts)

        return packet

    def put(self, packet: Message) -> None:
        if self.mode != "record":
            raise Exception(f"Can't use put() in {self.mode} mode")
        self._write(packet)

    def read_all(self) -> tuple[list[float], list[Message]]:
        """Returns a list of all the packets contained in the file and a list of the save times for the packets."""
        # TODO: make random access-like reading possible:
        # TODO: -seekable
        # TODO: -after opening, create an index of the start of each timestamp-time-packet triplet
        # TODO: -then make it seekable by time or by packet number.
        if self.mode != "playback":
            raise Exception(f"Can't use read_all() in {self.mode} mode")
        time_list = []
        packet_list = []
        while True:
            time, packet = self._read()
            if packet is None:
                break
            packet_list.append(packet)
            time_list.append(time)
        return time_list, packet_list

    def close(self) -> None:
        self.file_io.close()

    def _read_varint(self, offset: int = 0) -> int:
        """Read a varint from the stream."""
        if offset > 0:
            self.file_io.seek(offset)
        buf: bytes = self.file_io.read(1)
        if buf == b"":
            raise EOFError("unexpected EOF")
        while (buf[-1] & 0x80) >> 7 == 1:  # while the MSB is 1
            new_byte = self.file_io.read(1)
            if new_byte == b"":
                raise EOFError("unexpected EOF")
            buf += new_byte
        varint, _ = _DecodeVarint(buf, 0)
        return varint

    def _read(self) -> tuple[float, Message] | tuple[None, None]:
        """
        Read a single length-delimited message from the stream.

        Similar to:
        * [`CodedInputStream`](https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/io/coded_stream.h#L66)
        * [`parseDelimitedFrom()`](https://github.com/protocolbuffers/protobuf/blob/master/java/core/src/main/java/com/google/protobuf/Parser.java)

        A .protorec file is a repetition of the following fields:
            timestamp (double float = 8 bytes) +
            message_type (1 byte) +
            message length (varint) +
            protbuf message (message length bytes)
        """
        # reading the next message and its metadata
        time_b = self.file_io.read(8)
        if len(time_b) == 0:
            return None, None  # reached EOF
        timestamp = struct.unpack("<d", time_b)[0]
        msg_type = str(self.file_io.read(1), "utf-8")
        size = self._read_varint()
        buf = self.file_io.read(size)

        try:
            # decoding the message based on the msg_type byte
            msg = DataType.to_message(DataType(msg_type))
            msg.ParseFromString(buf)
        except Exception as e:
            current_pos = self.file_io.tell()
            self.file_io.seek(0, 2)
            file_length = self.file_io.tell()
            print(
                f"Message parsing has thrown an error. Probably because of an unsupported packet type or an abrupt EOF. Reading protorec terminates now. \nPacket data:"
                f"\n\trecording time={timestamp:2.7f};"
                f"\n\tmessage type={msg_type};"
                f"\n\trecorded packet size={size}, file IO read buffer size={len(buf)} (these should be equal);"
                f"\n\tfile pointer position={f'{current_pos:,.0f}'.replace(',','.')}, file length= {f'{file_length:,.0f}'.replace(',','.')}"
                f"\n ERROR MESSAGE: {e}"
            )
            return None, None  # reached EOF
        return timestamp, msg

    def _write(self, msg: Message) -> None:
        """
        Write a single length-delimited message to the stream.

        Similar to:
        * [`CodedOutputStream`](https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/io/coded_stream.h#L47)
        * [`MessageLite#writeDelimitedTo`](https://github.com/protocolbuffers/protobuf/blob/master/java/core/src/main/java/com/google/protobuf/MessageLite.java#L126)
        """
        time_b = struct.pack("<d", time())
        assert self.file_io is not None
        msg_type = DataType.from_message(msg).value.encode("utf-8")
        self.file_io.write(time_b)
        self.file_io.write(msg_type)
        # write the length of the message to the filestream in varint representation
        _EncodeVarint(self.file_io.write, msg.ByteSize())
        self.file_io.write(msg.SerializeToString())
