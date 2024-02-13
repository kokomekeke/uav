import zmq
import time

from logging import getLogger


_INIT_GROUP = "init"
_INIT_CONFIRM = "OK"

# Parameters for message message ID, sent as a message header
_ID_LENGTH = 4
_ID_ENCODING = "little"


class REQ:
    """UDP-based REQUEST client"""

    def __init__(
            self,
            address_client: str = "127.0.0.1",
            address_server: str = "127.0.0.1",
            port_client: int = 5555,
            port_server: int = 5556,
            group_request: str = "q",
            group_response: str = "p"
    ) -> None:
        self._logger = getLogger(self.__class__.__name__)

        # Make sure groups don't conflict with init group
        if group_request == _INIT_GROUP:
            group_request = "q"
            self._logger.warning(f"Invalid group name: \"{group_request}\". group_request set to \"q\"")
        if group_response == _INIT_GROUP:
            group_response = "p"
            self._logger.warning(f"Invalid group name: \"{group_response}\". group_request set to \"p\"")

        self._address_client = address_client
        self._address_server = address_server
        self._port_client = port_client
        self._port_server = port_server
        self._group_request = group_request
        self._group_response = group_response

        # Define up- and downstream channels
        self._context = zmq.Context()
        self._radio = self._context.socket(zmq.RADIO)
        self._dish = self._context.socket(zmq.DISH)

        # Set up message tracking ID
        self._message_id = 0

    def connect(self, timeout: int = 10000) -> bool:
        """Connect and bind up- and downstream sockets
        
        Sends init message to server if and only if address_client is provided.
        Connection parameters should not be changed afterwards.
        """

        self._radio.connect(f"udp://{self._address_server}:{self._port_server}")
        self._dish.bind(f"udp://*:{self._port_client}")
        self._dish.join(self._group_response)

        # Send INIT message
        if self._address_client is not None:
            return self._init(timeout)
        else:
            return True
    
    def _init(self, timeout: int = 10000) -> bool:
        """Send init message to server and return whether it succeeded"""

        init = f"{self._address_client}:{self._port_client}"
        
        self._dish.leave(self._group_response.encode())
        self._dish.join(_INIT_GROUP)

        result = False
        start = time.time_ns()
        while (time.time_ns()-start)/1e6 < timeout:
            self._radio.send(init.encode(), group=_INIT_GROUP)

            if self._dish.poll(timeout=0):
                result = self._dish.recv().decode()
                break
        
        self._dish.leave(_INIT_GROUP.encode())
        self._dish.join(self._group_response)

        return result == _INIT_CONFIRM

    def send(self, message: bytes, timeout: int = 1000) -> bytes:
        """Send request. Hang until response arrives or timeout is reached"""

        # Make sure incoming buffer is empty
        #while self._dish.poll(timeout=0):
        #    self._dish.recv()
        
        # Send message
        id = self._message_id.to_bytes(_ID_LENGTH, _ID_ENCODING)
        self._radio.send(id+message, group=self._group_request)

        # Wait for response
        response = None
        start = time.time_ns()
        while (time.time_ns()-start)/1e6 < timeout:
            remaining = timeout-(time.time_ns()-start)/1e6
            if self._dish.poll(timeout=remaining):
                message = self._dish.recv()

                # Check if response actually belongs to the current request
                id = int.from_bytes(message[:_ID_LENGTH], _ID_ENCODING)
                if id == self._message_id:
                    response = message[_ID_LENGTH:]
                    break
                else:
                    self._logger.debug(f"Dropped outdated message")
        
        self._message_id += 1
        return response


class REP:
    """UDP-based REPLY server"""

    def __init__(self,
            address_client: str = None,
            port_client: int = None,
            port_server: int = 5556,
            group_request: str = "q",
            group_response: str = "p"
    ) -> None:
        self._logger = getLogger(self.__class__.__name__)

        # Make sure groups don't conflict with init group
        if group_request == _INIT_GROUP:
            group_request = "q"
            self._logger.warning(f"Invalid group name: \"{group_request}\". group_request set to \"q\"")
        if group_response == _INIT_GROUP:
            group_response = "p"
            self._logger.warning(f"Invalid group name: \"{group_response}\". group_request set to \"p\"")
        
        self._address_client = address_client
        self._port_client = port_client
        self._port_server = port_server
        self._group_request = group_request
        self._group_response = group_response

        # Define up- and downstream channels
        self._context = zmq.Context()
        self._radio = self._context.socket(zmq.RADIO)
        self._dish = self._context.socket(zmq.DISH)

        # Message ID for detecting mismatched responses on client side
        self._message_id = None

    def connect(self, timeout: int = 10000) -> bool:
        """Connect and bind up- and downstream sockets
        
        If address_client and port_client is set to None, hangs until init message is received or timeout is reached
        """
        
        self._dish.bind(f"udp://*:{self._port_server}")
        self._dish.join(self._group_request)

        if self._address_client is not None and self._port_client is not None:
            self._radio.connect(f"udp://{self._address_client}:{self._port_client}")

            return True
        else:
            return self._init(timeout=timeout)
    
    def _init(self, timeout: int = 10000) -> bool:
        """Wait for init message and accept connection"""

        # Preapre for receiving init message
        self._dish.leave(self._group_request.encode())
        self._dish.join(_INIT_GROUP)

        # Wait for init message
        success = False
        if self._dish.poll(timeout=timeout):
            # Retrieve client address
            parts = self._dish.recv().decode().split(":")
            self._address_client = parts[0]
            self._port_client = int(parts[1])

            # Connect to client and send confirmation
            self._radio.connect(f"udp://{self._address_client}:{self._port_client}")
            self._radio.send(_INIT_CONFIRM.encode(), group=_INIT_GROUP)
            
            success = True
        
        # Prepare to receive normal communication
        self._dish.leave(_INIT_GROUP.encode())
        self._dish.join(self._group_request)

        return success
    
    def recv(self, timeout: int = None):
        """Read next incoming message. Hang until received or timeout is reached"""

        if self._message_id is not None:
            #TODO: Choose a more fitting exception
            raise Exception("Not in receive mode. Waiting for response.")

        if self._dish.poll(timeout=timeout):
            message = self._dish.recv()
            self._message_id = int.from_bytes(message[:_ID_LENGTH], _ID_ENCODING)

            return message[_ID_LENGTH:]
        
        return None
    
    def resp(self, message: bytes):
        """Send response to request."""

        if self._message_id is None:
            #TODO: Choose a more fitting exception
            raise Exception("Nothing to respond to.")

        id = self._message_id.to_bytes(_ID_LENGTH, _ID_ENCODING)
        self._radio.send(id+message, group=self._group_response)
        
        self._message_id = None
