from coloredlogs import install
from rich.logging import RichHandler
import logging

from typing import Optional
from pysagax.ui.custom_widgets import PopupWindow
import tkinter


def setup_logging(
    level: str = "INFO",
    show_process_name: bool = False,
    stream_handler: Optional[logging.Handler] = None,
) -> None:
    """Configure logging parameters"""
    # Validate logging level format
    if level is None:
        level = "INFO"
    if isinstance(level, str):
        level = level.upper()
    # return
    if stream_handler is None:
        stream_handler = RichHandler(rich_tracebacks=True)

    # Configure logging format
    format = "{asctime} {levelname:<5s} {name:<12s} {message}"
    if show_process_name:
        format = "[{processName}] " + format
    install(level=level, fmt=format, style="{")

    # TODO: Implement log files
    # TODO: this is the same function thats used in pysagaxUAV


class LoggerWindow(logging.Handler):
    def __init__(self, tkinter_root, log_level="INFO", open_window_level="WARNING"):
        """
        log_level: str or int, minimum log message level to store and display
        open_window_level: str or int, minimum log message level to automatically open the log window
        """
        logging.Handler.__init__(self)
        self.stringvar = tkinter.StringVar()
        self.window: Optional[PopupWindow] = None
        self.tkinter_root: tkinter.Tk = tkinter_root

        self.setLevel(log_level)
        self.open_window_level = (
            open_window_level
            if isinstance(open_window_level, int)
            else logging.getLevelName(open_window_level)
        )

        format = "{asctime} {levelname:<10s} {name:<12s} \n{message}"
        self.setFormatter(logging.Formatter(format, style="{"))

    def emit(self, record: logging.LogRecord):
        """Process incoming log messages"""
        record_str = self.format(record)
        self.stringvar.set(self.stringvar.get() + "\n\n\n" + record_str)
        if record.levelno >= self.open_window_level:
            self.show_log_window(dont_bring_forward=True)

    def on_window_closed(self):
        """Callback that is to be called when the window is closed"""
        self.window = None

    def show_log_window(self, dont_bring_forward=False):
        """Open log window"""
        if self.window is None:
            self.stringvar.set(
                self.stringvar.get().strip()
            )  # delete leading whitespace
            self.window = PopupWindow(
                self.tkinter_root,
                self.stringvar,
                title="Spotclient Logs",
                on_close_callback=self.on_window_closed,
            )
        elif not dont_bring_forward:
            self.window.bring_to_front()
