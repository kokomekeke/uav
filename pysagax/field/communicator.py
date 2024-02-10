from queue import Queue

# TODO: Fix imports with proper package structure
import sys, os

# sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))


from pysagax.field.loop import Loop
from pysagax.field.zmq_server import ZmqFieldServer


class Communicator(Loop):
    """Background process receiving commands and pushing then to internal queue"""

    def __init__(self, queue_in: Queue, queue_out: Queue, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Set up command channel
        self._server = ZmqFieldServer()
        self._queue_in = queue_in
        self._queue_out = queue_out

    def _pre_loop(self) -> None:
        # Connect and bind communication ports
        self._server.connect()

    def _loop(self) -> None:
        # Hang until a new command is received
        command = self._server.recv()
        self._logger.debug("Command received")

        # Send command to Interpreter
        self._queue_out.put(command)

        # Wait for response from Interpreter
        self._logger.debug("==========")
        response = self._queue_in.get()

        # Send response to remote client
        self._server.resp(response)
        self._logger.debug("Response sent")
