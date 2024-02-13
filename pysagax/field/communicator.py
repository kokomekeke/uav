from queue import Queue
from typing import Any, Optional

from pysagax.field.loop import Loop
from pysagax.communication.req_rep import REP


class Communicator(Loop):
    """Background process receiving commands and pushing then to internal queue"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Set up command channel
        self._server: Optional[REP] = None
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None

    def __call__(
        self, queue_in: Queue[Any], queue_out: Queue[Any], *args, **kwargs
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out
        self._server = REP()

        return super()._call(*args, **kwargs)

    def _pre_loop(self) -> None:
        # Connect and bind communication ports
        assert self._server is not None
        self._server.connect()

    def _loop(self) -> None:
        assert self._server is not None
        assert self._queue_in is not None
        assert self._queue_out is not None
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
