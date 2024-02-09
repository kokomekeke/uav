import zmq

class REQ:
    """UDP-based REQUEST client"""

    def __init__(
            self,
            address: str = "127.0.0.1",
            port_in: int = 5556,
            port_out: int = 5555
    ) -> None:
        
        self._address = address
        self._port_in = port_in
        self._port_out = port_out

        # Define up- and downstream channels
        self._context = zmq.Context()
        self._radio = self._context.socket(zmq.RADIO)
        self._dish = self._context.socket(zmq.DISH)

    def connect(self):
        """Connect and bind up- and downstream sockets"""

        self._radio.connect(f"udp://{self._address}:{self._port_out}")
        self._dish.bind(f"udp://*:{self._port_in}")
        self._dish.join("response")

    def send(self, message: bytes, timeout: int = 1000) -> bytes:
        """Send request. Hang until response arrives or timeout is reached"""

        # Make sure incoming buffer is empty
        while self._dish.poll(timeout=0):
            self._dish.recv()
        
        self._radio.send(message, group="command")

        if self._dish.poll(timeout=timeout):
            return self._dish.recv()
        else:
            return None

