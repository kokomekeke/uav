import zmq


class SUB:
    def __init__(
        self, address_server: str = "127.0.0.1", port_server: int = 5556, **kwargs
    ) -> None:
        self._address_server = address_server
        self._port_server = port_server

        self._connected = False
        self._context = zmq.Context()

    def connect(self, **kwargs):
        self._subscriber = self._context.socket(zmq.SUB)
        self._subscriber.connect(f"tcp://{self._address_server}:{self._port_server}")
        self._subscriber.subscribe("")
        self._connected = True

        return True

    def disconnect(self, **kwargs):
        self._subscriber.setsockopt(zmq.LINGER, 0)
        self._subscriber.close()
        self._connected = False

    def receive(self, timeout: int = 1000):

        if not self._connected:
            raise Exception("Not connected")
        if (self._subscriber.poll(timeout) & zmq.POLLIN) != 0:
            return self._subscriber.recv()
        else:
            self.disconnect()
            self.connect()

        return None

    def recv(self, timeout: int = 1000) -> tuple[bytes, str] | None:
        recv_raw = self.receive(timeout)
        if recv_raw is not None:
            return bytes(recv_raw[1:]), str(recv_raw[0:1].decode())
        else:
            return None


class PUB:
    def __init__(self, port_server: int = 5556, **kwargs) -> None:
        self._port_server = port_server

        self._context = zmq.Context()

    def connect(self, **kwargs):
        self._publisher = self._context.socket(zmq.PUB)
        self._publisher.bind(f"tcp://*:{self._port_server}")

        return True

    def publ(self, message: bytes):
        self._publisher.send(message)
