from queue import Queue
import queue
from typing import Any, Optional, Type
from pysagax.communication.broadcast import TX

from pysagax.field.loop import Loop
import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
from pysagax.message.data_types import DataType


class StreamerServer:
    def __init__(self, server: TX, level: int, timeout: int) -> None:
        self.server = server
        self.level = level
        self.timeout = timeout


class Streamer(Loop):
    """Background process sending stream packets to client"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Set up command channel
        self._servers: dict[str, StreamerServer] = {}
        self._queue_in: Optional[Queue[Any]] = None
        self._conf_in: Optional[Queue[Any]] = None

        self._levels: dict[int, list[DataType]] = {
            0: [],  # TODO Heartbeat
            1: [DataType.TELEMETRY],  # Telemetry
            2: [DataType.TELEMETRY, DataType.EVENT, DataType.ERROR],
            3: [
                DataType.TELEMETRY,
                DataType.EVENT,
                DataType.ERROR,
                DataType.MEASUREMENT,
            ],
        }

    def __call__(
        self, queue_in: Queue[Any], conf_in: Queue[Any], *args, **kwargs
    ) -> None:
        self._queue_in = queue_in
        self._conf_in = conf_in
        return super()._call(*args, **kwargs)

    def _pre_loop(self) -> None:
        # Connect and bind communication ports
        pass

    def add_stream_client(self, target: proto_cmd.StreamTarget) -> None:
        self._servers[f"{target.address}:{target.port}"] = StreamerServer(
            TX(target.address, port=target.port), int(target.level), 0
        )
        self._servers[f"{target.address}:{target.port}"].server.connect()
        self._logger.info(f"Stream client {target.address}:{target.port} added")

    def remove_stream_client(self, target: proto_cmd.StreamTarget) -> None:
        self._servers[f"{target.address}:{target.port}"].server.disconnect()
        del self._servers[f"{target.address}:{target.port}"]
        self._logger.info(f"Stream client {target.address}:{target.port} removed ")

    def _loop(self) -> None:
        # Wait for response from Interpreter
        assert self._queue_in is not None
        assert self._conf_in is not None
        try:
            command = self._conf_in.get(block=False)
            self._logger.debug("Got command packet")
            if isinstance(command, proto_cmd.Command):
                match command.instruction:
                    case proto_cmd.STREAM_START:
                        self.add_stream_client(command.target)
                    case proto_cmd.STREAM_STOP:
                        self.remove_stream_client(command.target)
                return
        except queue.Empty:
            pass
        try:
            packet = self._queue_in.get(block=True, timeout=1)
            self._logger.debug(f"Got {type(packet).__name__} stream packet")
            # Send response to remote client
            stream_packet = packet.SerializeToString()
            type_field_enum = DataType.from_message(packet)
            if type_field_enum is None:
                self._logger.warning(
                    f"Cannot send packet type {type(packet).__name__} on Stream"
                )
                return
            type_field = DataType(type_field_enum)
            for host_port, server in self._servers.items():
                if type_field not in self._levels[server.level]:
                    self._logger.debug(
                        f"{packet.DESCRIPTOR.name} ({type_field.name} -> {type_field.value}) packet not sent to {host_port} level {server.level}"
                    )
                    continue

                server.server.send(stream_packet, type_field.value)
                self._logger.debug(
                    f"{packet.DESCRIPTOR.name} ({type_field.name} -> {type_field.value}) packet sent to {host_port} level {server.level}"
                )
        except queue.Empty:
            pass
