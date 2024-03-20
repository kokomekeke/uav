from __future__ import annotations
from queue import Queue

from typing import Optional
from pysagax.df.lena_core_service import CoreServiceParser

from pysagax.common.loop import Loop


class CSParser(Loop, CoreServiceParser):

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)
        CoreServiceParser.__init__(self)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None

    def __call__(
        self,
        queue_in: Queue[bytes],
        queue_out: Queue[bytes],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out
        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None
        data = self._queue_in.get(block=True)
        for cs_packet in self.extract_packets(data):
            self._queue_out.put(cs_packet)
