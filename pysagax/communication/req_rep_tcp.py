import zmq


class REQ:
    def __init__(
            self,
            address_server: str = "127.0.0.1",
            port_server: int = 5556,
            **kwargs
    ) -> None:
        self._address_server = address_server
        self._port_server = port_server

        self._connected = False
        self._context = zmq.Context()
    
    def connect(self, **kwargs):
        self._request = self._context.socket(zmq.REQ)
        self._request.connect(f"tcp://{self._address_server}:{self._port_server}")
        self._connected = True

        # For compatibility with UDP-based REQ-REP
        return True
    
    def disconnect(self, **kwargs):
        self._request.setsockopt(zmq.LINGER, 0)
        self._request.close()
        self._connected = False
    
    def send(self, message: bytes, timeout: int = 1000):
        """Send request. Hang until response arrives or timeout is reached"""

        if not self._connected:
            raise Exception("Not connected")
        
        self._request.send(message)

        if (self._request.poll(timeout) & zmq.POLLIN) != 0:
            return self._request.recv()
        else:
            self.disconnect()
            self.connect()
        
        return None


class REP:
    def __init__(
            self,
            port_server: int = 5556,
            **kwargs
    ) -> None:
        self._port_server = port_server

        self._context = zmq.Context()
    
    def connect(self, **kwargs):
        self._reply = self._context.socket(zmq.REP)
        self._reply.bind(f"tcp://*:{self._port_server}")

        # For compatibility with UDP-based REQ-REP
        return True
    
    def recv(self, timeout: int | None = None):
        if (self._reply.poll(timeout) & zmq.POLLIN) != 0:
            return self._reply.recv()
        
        return None

    def resp(self, message: bytes):
        self._reply.send(message)
