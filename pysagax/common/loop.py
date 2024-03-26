from logging import getLogger
from signal import signal, SIGINT, SIGTERM
from os import kill, getpid
import traceback


class Loop:
    """Base class for infinitely looping background tasks"""

    def __init__(self, level: str = "INFO") -> None:
        self._logger = getLogger(self.__class__.__name__)
        self._logger.setLevel(level.upper())

        # Set up terminating signals
        signal(SIGINT, self._signal_handler)
        signal(SIGTERM, self._signal_handler)

    def _call(self, *args, **kwargs) -> None:
        """Execute the main logic of the loop"""
        try:
            self._logger.info(f"Loop (Pid {getpid()})")
            self._pre_loop()

            self._logger.debug(f"Running main loop (Pid {getpid()})")
            while True:
                self._loop()
        except Exception as e:
            self._logger.critical(" / ".join(traceback.format_exception(e)))
            self._quit()
            raise

    def _pre_loop(self) -> None:
        """Called before main loop starts. Used for initialization"""

        # Override this function
        pass

    def _loop(self) -> None:
        """The main logic of the loop. This method is called inside a while loop"""

        # Override this function
        pass

    def _signal_handler(self, signal, frame) -> None:
        """Handle incoming signals"""

        getLogger("Loop").info(f"Received signal {signal} (Pid {getpid()}), exiting...")
        self._quit()

    def _quit(self) -> None:
        """Stop execution of loop logic"""

        # Kill loop forcefully
        kill(getpid(), 9)
