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

from pysagax.message.data_types import DataType

T = TypeVar("YourProtoClass", bound=Message)  # TODO

FileStreamMode: TypeAlias = Literal["record", "playback"]


class FileStreamer:
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

        # for playback timing. The difference of the first packets read time and save time
        self._stream_delay: Optional[float] = None

        self._packet_buffer = None
        self._ts_buffer = None

    def get(self, timeout=1):
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

    def put(self, packet):
        if self.mode != "record":
            raise Exception(f"Can't use put() in {self.mode} mode")
        # TODO: assert isinstance(packet
        # TODO: add option to cast measurment/spectrum to int16 for saving disk space
        self._write(packet)

    def read_all(self):
        if self.mode != "playback":
            raise Exception(f"Can't use read_all() in {self.mode} mode")
        pass

    def close(self):
        self.file_io.close()

    def _read_varint(self, offset: int = 0) -> Optional[int]:
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

    def _read(self):  # TODO typing,  -> Optional[T]:
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
        time_b = self.file_io.read(8)
        if len(time_b) == 0:
            return None, None  # reached EOF
        timestamp = struct.unpack("<d", time_b)[0]
        msg_type = str(self.file_io.read(1), "utf-8")
        size = self._read_varint()
        buf = self.file_io.read(size)
        msg = DataType.to_message(DataType(msg_type))
        # msg = proto_class_name()
        msg.ParseFromString(buf)
        return timestamp, msg

    def _write(self, msg: T):
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
        _EncodeVarint(self.file_io.write, msg.ByteSize())
        self.file_io.write(msg.SerializeToString())
