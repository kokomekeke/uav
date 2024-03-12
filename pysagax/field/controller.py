from queue import Queue

from loop import Loop

class CSController(Loop):
    """Background process communicating with CoreService command interface"""

    def __init__(
            self,
            queue_in: Queue,
            queue_out: Queue,
            #TODO: Define useful defaults
            address: str = "127.0.0.1",
            port: int = 4242,
            *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        self._queue_in = queue_in
        self._queue_out = queue_out

        #TODO: Set up control channel to CoreService here
    
    def _pre_loop(self) -> None:
        pass

        #TODO: Connect to CoreService here
    
    def _loop(self) -> None:
        # Hang until a new command is received
        command = self._queue_in.get()

        #TODO: Send command to CoreService and collect response
        self._logger.debug(command)
        response = "132"

        # Send response to Interpreter
        self._queue_out.put(response)
