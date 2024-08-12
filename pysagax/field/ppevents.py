from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue

from typing import Any, Optional

import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading

from pysagax.common.loop import Loop

from pysagax.util.queue_put import queue_put

class PPEvents(Loop):
    """
    Background process for detecting ComInt events.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out

        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None

        try:
            packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(packet, proto_data.Measurement)

            #TODO

            self._logger.debug(f"PostProcessing/Events finished on packet {packet.packet_id}")
            queue_put(self._queue_out, packet, timeout=0.1, logger=self._logger)

        except queue.Empty:
            pass
