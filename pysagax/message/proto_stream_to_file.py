"""A read/write library for length-delimited protobuf messages



BASED ON: https://pypi.org/project/delimited-protobuf/"""
from __future__ import absolute_import

from typing import BinaryIO, Literal, Optional, Type, TypeAlias, TypeVar

from google.protobuf.internal.decoder import _DecodeVarint
from google.protobuf.internal.encoder import _EncodeVarint
from google.protobuf.message import Message

from pysagax.message.data_types import DataType

T = TypeVar('YourProtoClass', bound=Message)#TODO

FileStreamMode: TypeAlias = Literal["record", "playback"]

class FileStreamer():
    def __init__(self, path: str, mode: FileStreamMode) -> None:
        self.path = path
        self.mode = mode

        # TODO check for path, maybe create file if doesn't exist. Overwrite or append to existing file?
        if self.mode == "record":
            self.file_io = open(self.path, 'w+b')
        elif self.mode == "playback":
            self.file_io = open(self.path, 'rb')
        else:
            raise Exception(f"Undefined FileStreamMode '{self.mode}'")

    def get(self, timeout = 1):
        if self.mode != "playback":
            raise Exception(f"Can't use get() in {self.mode} mode")
        # TODO: timout
        return self._read()
    
    def put(self, packet):
        if self.mode != "record":
            raise Exception(f"Can't use put() in {self.mode} mode")
        # assert isinstance(packet 
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
        if buf == b'':
            print("EOF")
            return None  # reached EOF
        while (buf[-1] & 0x80) >> 7 == 1:  # while the MSB is 1
            new_byte = self.file_io.read(1)
            if new_byte == b'':
                raise EOFError('unexpected EOF')
            buf += new_byte
        varint, _ = _DecodeVarint(buf, 0)
        print(varint)
        return varint

    def _read(self):#,  -> Optional[T]:
        """
        Read a single length-delimited message from the stream.

        Similar to:
        * [`CodedInputStream`](https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/io/coded_stream.h#L66)
        * [`parseDelimitedFrom()`](https://github.com/protocolbuffers/protobuf/blob/master/java/core/src/main/java/com/google/protobuf/Parser.java)
        
        message_type (1 byte) + message length (varint) + protbuf message
        """
        msg_type = str(self.file_io.read(1), "utf-8")
        size = self._read_varint()
        if size is None:
            return None # reached EOF
        buf = self.file_io.read(size)
        msg = DataType.to_message(DataType(msg_type))
        # msg = proto_class_name()
        msg.ParseFromString(buf)
        return msg
    
    def _write(self, msg: T):
        """
        Write a single length-delimited message to the stream.

        Similar to:
        * [`CodedOutputStream`](https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/io/coded_stream.h#L47)
        * [`MessageLite#writeDelimitedTo`](https://github.com/protocolbuffers/protobuf/blob/master/java/core/src/main/java/com/google/protobuf/MessageLite.java#L126)
        """
        assert self.file_io is not None
        msg_type = DataType.from_message(msg).value.encode('utf-8')
        self.file_io.write(msg_type)
        _EncodeVarint(self.file_io.write, msg.ByteSize())
        self.file_io.write(msg.SerializeToString())


# def _read_varint(stream: BinaryIO, offset: int = 0) -> Optional[int]:
#     """Read a varint from the stream."""
#     if offset > 0:
#         stream.seek(offset)
#     buf: bytes = stream.read(1)
#     if buf == b'':
#         print("EOF")
#         return None  # reached EOF
#     while (buf[-1] & 0x80) >> 7 == 1:  # while the MSB is 1
#         new_byte = stream.read(1)
#         if new_byte == b'':
#             raise EOFError('unexpected EOF')
#         buf += new_byte
#     varint, _ = _DecodeVarint(buf, 0)
#     print(varint)
#     return varint


# def read(stream: BinaryIO):#, proto_class_name: Type[T]) -> Optional[T]:
#     """
#     Read a single length-delimited message from the given stream.

#     Similar to:
#       * [`CodedInputStream`](https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/io/coded_stream.h#L66)
#       * [`parseDelimitedFrom()`](https://github.com/protocolbuffers/protobuf/blob/master/java/core/src/main/java/com/google/protobuf/Parser.java)
    
#     message_type (1 byte) + message length (varint) + protbuf message
#     """
#     msg_type = str(stream.read(1), "utf-8")
#     size = _read_varint(stream)
#     if size is None:
#         return None # reached EOF
#     buf = stream.read(size)
#     msg = DataType.to_message(DataType(msg_type))
#     # msg = proto_class_name()
#     msg.ParseFromString(buf)
#     return msg


# def write(stream: BinaryIO, msg: T):
#     """
#     Write a single length-delimited message to the given stream.

#     Similar to:
#       * [`CodedOutputStream`](https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/io/coded_stream.h#L47)
#       * [`MessageLite#writeDelimitedTo`](https://github.com/protocolbuffers/protobuf/blob/master/java/core/src/main/java/com/google/protobuf/MessageLite.java#L126)
#     """
#     assert stream is not None
#     msg_type = DataType.from_message(msg).value.encode('utf-8')
#     stream.write(msg_type)
#     _EncodeVarint(stream.write, msg.ByteSize())
#     stream.write(msg.SerializeToString())