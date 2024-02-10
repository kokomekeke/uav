import zmq


class ZmqFieldServer:
    """UDP-based REPLY server"""

    def __init__(
        self, address: str = "127.0.0.1", port_in: int = 5555, port_out: int = 5556
    ) -> None:
        self._address = address
        self._port_in = port_in
        self._port_out = port_out

        # Define up- and downstream channels
        self._context = zmq.Context()
        self._radio = self._context.socket(zmq.RADIO)
        self._dish = self._context.socket(zmq.DISH)

        # Switch ensuring that a request is responded to before the next request
        self._receiving = True

    def connect(self):
        """Connect and bind up- and downstream sockets"""

        self._radio.connect(f"udp://{self._address}:{self._port_out}")
        self._dish.bind(f"udp://*:{self._port_in}")
        self._dish.join("command")

    def recv(self, timeout: int = None):
        """Read next incoming message. Hang until received or timeout is reached"""

        if not self._receiving:
            raise Exception("Not in receive mode. Waiting for response.")

        if self._dish.poll(timeout=timeout):
            self._receiving = False
            return self._dish.recv()
        else:
            return None

    def resp(self, message: bytes):
        """Send response to request."""

        if self._receiving:
            raise Exception("Nothing to respond to.")

        self._radio.send(message, group="response")
        self._receiving = True
