import zmq

from logging import getLogger
from typing import Tuple
from google.protobuf.message import Message

# Empirical size limit of messages, based on local testing
# MESSAGE_LIMIT = 16301 # This much can be sent
MESSAGE_LIMIT = 8101  # This much can be received


class RX:
    def __init__(self, port: int = 4242) -> None:
        self._logger = getLogger("RX")

        self._port = port

        self._context = zmq.Context()
        self._dish = self._context.socket(zmq.DISH)

    def connect(self, group: str | list[str]) -> None:
        address = f"udp://*:{self._port}"
        self._logger.debug(f"Connecting to {address}")
        self._dish.bind(address)

        self.join(group)

    def join(self, group: str | list[str]) -> None:
        if not isinstance(group, list):
            group = [group]

        for g in group:
            self._logger.debug(f"Joining group {g}")
            self._dish.join(g)

    def leave(self, group: str | list[str]):
        if not isinstance(group, list):
            group = [group]

        for g in group:
            self._logger.debug(f"Leaving group {g}")
            self._dish.leave(g)

    def recv(self, timeout: int | None = None) -> Tuple[bytes, str] | None:
        if self._dish.poll(timeout=timeout):
            frame = self._dish.recv(copy=False)
            return frame.bytes, frame.group
        else:
            return None, None


class TX:
    def __init__(
            self,
            address: str = "127.0.0.1",
            port: int = 5353
    ) -> None:
        self._logger = getLogger("TX")

        self._address = address
        self._port = port

        self._context = zmq.Context()
        self._radio = self._context.socket(zmq.RADIO)

    def connect(self) -> None:
        self._radio.connect(f"udp://{self._address}:{self._port}")

    def disconnect(self) -> None:
        self._radio.disconnect(f"udp://{self._address}:{self._port}")

    def send(self, data: bytes, group="default") -> None:
        if len(data) > MESSAGE_LIMIT:
            raise BufferError(f"Data too large. Keep it under {MESSAGE_LIMIT}.")
        self._radio.send(data, group=group)
