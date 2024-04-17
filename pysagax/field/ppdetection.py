from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue

from typing import Any, Optional

import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading

from pysagax.common.loop import Loop


class PPDetection(Loop):
    """
    Background process for ROI detection and data aggregation on measurement packets.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._conf_queue_in: Optional[Queue] = None
        self._conf_queue_out: Optional[Queue] = None

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        conf_queue_in: Queue[Any],
        conf_queue_out: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out
        self._conf_queue_in = conf_queue_in
        self._conf_queue_out = conf_queue_out

        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None
        assert self._conf_queue_in is not None
        assert self._conf_queue_out is not None

        # Hang until a new command is received
        try:
            conf_request = self._conf_queue_in.get(timeout=0, block=False)
            self._protobuf_to_log(conf_request)
            self._conf_queue_out.put(None)
        except queue.Empty:
            pass

        try:
            packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(packet, proto_data.Measurement)

            #TODO

            self._logger.debug(f"PostProcessing/Detection finished on packet {packet.packet_id}")
            self._queue_out.put(packet)

        except queue.Empty:
            pass
