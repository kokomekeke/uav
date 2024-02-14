from enum import Enum
from queue import Queue
from re import I
from typing import Any, Optional
from pysagax.communication.broadcast import TX

from pysagax.field.loop import Loop
import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data

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
        self._queue_in: Optional[Queue] = None

    def __call__(self, queue_in: Queue[Any], *args, **kwargs) -> None:
        self._queue_in = queue_in
        return super()._call(*args, **kwargs)

    def _pre_loop(self) -> None:
        # Connect and bind communication ports
        pass
    
    def add_stream_client(self, target: Any) -> None:
        self._servers[f"{target.address}:{target.port}"] = StreamerServer(TX(address=address, port=port), int(target.level), 0)
        self._servers[f"{target.address}:{target.port}"].server.connect()  
    
    def remove_stream_client(self, target: Any) -> None:
        self._servers[f"{target.address}:{target.port}"].server.disconnect()
        del self._servers[f"{target.address}:{target.port}"]


    def _loop(self) -> None:
        # Wait for response from Interpreter
        packet = self._queue_in.get()
        if isinstance(packet, proto_cmd.Command):
            match packet.instruction:
                case proto_cmd.STREAM_START:
                    self.add_stream_client(command.target)
                case proto_cmd.STREAM_STOP:
                    self.remove_stream_client(command.target)
            return 

        # Send response to remote client
        for host_port, server in self._servers.items():
            stream_packet = packet.SerializeToString()
            server.server.send(stream_packet)
            self._logger.debug(f"Stream packet sent to {host_port}")
