from queue import Queue
import queue
from typing import Any, Optional
from pysagax.communication.broadcast import TX

from pysagax.field.loop import Loop
import pysagax.message.command_pb2 as proto_cmd


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
            self._logger.debug("Got stream packet")
            # Send response to remote client
            for host_port, server in self._servers.items():
                stream_packet = packet.SerializeToString()
                server.server.send(stream_packet)
                self._logger.debug(
                    f"{type(packet).__name__} packet sent to {host_port}"
                )
        except queue.Empty:
            pass
