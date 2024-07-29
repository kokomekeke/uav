from __future__ import annotations
import logging
from queue import Queue
import time

from typing import Optional

from pysagax.common.loop import Loop



class CIEvents(Loop):
    """Background process for connecting to the CoreService stream interface and receiving binary data from there"""

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)

    def __call__(
        self,
        *args,
        **kwargs,
    ) -> None:
        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        time.sleep(1000)
        pass
