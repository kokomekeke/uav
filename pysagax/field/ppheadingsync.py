from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue

from typing import Any, Optional

import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading

from pysagax.common.loop import Loop


class PPHeadingSync(Loop):
    """
    Background process for syncing CoreService stream packets and heading packets.
    The module also fills the config_id field of the measurement packets with the correct value
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._heading_queue_in: Optional[Queue] = None
        self._latest_config_id_value: Optional[ValueProxy[int]] = None
        self._latest_heading: Optional[proto_heading.HeadingData] = None

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        heading_queue_in: Queue[Any],
        latest_config_id_value: Optional[ValueProxy[int]] = None,
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out
        self._heading_queue_in = heading_queue_in
        self._latest_config_id_value = latest_config_id_value

        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None
        assert self._heading_queue_in is not None
        
        while True:
            try:
                heading_packet = self._heading_queue_in.get_nowait()
                if heading_packet is not None:
                    self._latest_heading = heading_packet
            except queue.Empty:
                break
        try:
            meas_packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(meas_packet, proto_data.Measurement)

            if self._latest_heading is not None:
                meas_packet.heading_data.CopyFrom(self._latest_heading)
            if self._latest_config_id_value is not None:
                meas_packet.config_id = self._latest_config_id_value.get()

            self._logger.debug(f"Syncing heading data finished on packet {meas_packet.packet_id}")
            self._queue_out.put(meas_packet)

        except queue.Empty:
            pass
