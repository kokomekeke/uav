import zmq

from logging import getLogger


# Empirical size limit of messages, based on local testing
MESSAGE_LIMIT = 16301 # This much can be sent
#MESSAGE_LIMIT = 8101  # This much can be received


class RX:
    def __init__(self, port: int = 4242, groups: [str] = None) -> None:
        self._logger = getLogger("RX")

        self._port = port
        self._groups = groups

        self._context = zmq.Context()
        self._dish = self._context.socket(zmq.DISH)
    
    def connect(self) -> None:
        address = f"udp://*:{self._port}"
        self._logger.debug(f"Connecting to {address}")
        self._dish.bind(address)

        self._logger.debug(f"Joining group *")
        for group in self._groups:
            self._dish.join(group)
    
    def recv(self, timeout: int | None = None) -> bytes:
        if self._dish.poll(timeout=timeout):
            return self._dish.recv()
        else:
            return None


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

    def send(self, data: bytes, group="*") -> None:
        if len(data) > MESSAGE_LIMIT:
            raise BufferError(f"Data too large. Keep it under {MESSAGE_LIMIT}.")
        self._radio.send(data, group=group)

