from queue import Queue
from typing import Any, Optional
from pysagax.communication.broadcast import TX

from pysagax.field.loop import Loop


class Streamer(Loop):
    """Background process sending stream packets to client"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Set up command channel
        self._servers: dict[str, TX] = {}
        self._queue_in: Optional[Queue] = None

    def __call__(self, queue_in: Queue[Any], *args, **kwargs) -> None:
        self._queue_in = queue_in
        return super()._call(*args, **kwargs)

    def add_conn(self, address: str, port: int) -> None:
        self._servers[f"{address}:{port}"] = TX(address=address, port=port)
        self._servers[f"{address}:{port}"].connect()

    def _pre_loop(self) -> None:
        # Connect and bind communication ports
        pass

    def _loop(self) -> None:
        # Wait for response from Interpreter
        stream_packet = self._queue_in.get()

        # Send response to remote client
        for host_port, server in self._servers.items():
            server.send(stream_packet)
            self._logger.debug(f"Stream packet sent to {host_port}")
