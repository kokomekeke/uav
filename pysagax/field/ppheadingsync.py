from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue
from collections import deque


from typing import Any, Optional

import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading

from pysagax.util.queue_put import queue_put

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

        # deque for storing 2 {delta_t, heading_data} pairs, where
        # delta_t is the time difference between the current measurement packet and the heading packet
        self.heading_deque: deque = deque(maxlen=2)
        self.heading_deque.extend(
            [{"delta_t": float("inf"), "data": proto_heading.HeadingData()}] * 2
        )

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

    def _update_delta_t(self, target_time: int) -> None:
        """
        Updates delta_t values for the heading packets that are currently in the deque.

        PPHeadingSync was designed to work on chronologically ordered packets. This method checks
          the ordering so that a corrupted incoming stream doesn't halts the syncing.
        """
        current_oldest_ts = float("inf")
        for i in reversed(range(len(self.heading_deque))):
            heading: proto_heading.HeadingData = self.heading_deque[i]["data"]
            if heading.HasField("timestamp"):
                ts = heading.timestamp.ToNanoseconds()
                if ts > current_oldest_ts:
                    # packets should get older in reversed iteration, but this packet is newer
                    # don't use this packet
                    delta_t = float("inf")
                    self._logger.warning(
                        f"Heading data arrived in non-chronological order. The late packet will not be used."
                    )
                else:
                    # properly ordered data
                    delta_t = abs(target_time - ts)
                    current_oldest_ts = ts
                self.heading_deque[i]["delta_t"] = delta_t

    def _get_best_fitting_heading(
        self, target_time: int
    ) -> tuple[float | int, Optional[proto_heading.HeadingData]]:
        """
        A function for processing the incoming packets on heading_queue_in and finding the one that has a timestamp closest to target_time.
        This function assumes that packets arrive in chronological order on both self._heading_queue_in and self._queue_in.

        Parameters:
            target_time: a unix timestamp in nanoseconds

        Returns: a tuple of
            (
            delta_t: the best fitting heading packet's time difference to target_time,
            best_fit:    the best fitting HeadingData packet
            )
        """
        best_delta_t = float("inf")
        best_fit: Optional[proto_heading.HeadingData] = None
        while best_fit is None:
            # heading_deque[0] is always older than heading_deque[1]
            if self.heading_deque[0]["delta_t"] < self.heading_deque[1]["delta_t"]:
                # the older data is better than the new one ->
                # merge the older with the measurement and keep both headings for future measurements
                best_delta_t = self.heading_deque[0]["delta_t"]
                best_fit = self.heading_deque[0]["data"]
            else:
                # the newer data is better than the older
                # -> try to get an even newer and throw out the old packet
                try:
                    heading_packet: proto_heading.HeadingData = (
                        self._heading_queue_in.get_nowait()
                    )
                    if heading_packet is None:
                        break
                    delta_t = abs(
                        target_time - heading_packet.timestamp.ToNanoseconds()
                    )
                    self.heading_deque.append(
                        {"delta_t": delta_t, "data": heading_packet}
                    )
                except queue.Empty:
                    # no more heading packets in the queue -> the newer is the best fit
                    best_delta_t = self.heading_deque[1]["delta_t"]
                    best_fit = self.heading_deque[1]["data"]
        return best_delta_t, best_fit

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None
        assert self._heading_queue_in is not None

        try:
            # get new measurement packet
            meas_packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(meas_packet, proto_data.Measurement)

            target_time = meas_packet.time.ToNanoseconds()
            self._update_delta_t(target_time)
            delta_t, best_fit = self._get_best_fitting_heading(target_time)

            if best_fit is not None:
                meas_packet.heading_data.CopyFrom(best_fit)

            if self._latest_config_id_value is not None:
                meas_packet.config_id = self._latest_config_id_value.get()

            self._logger.debug(
                f"Heading and measurement packets merged with a time difference of {delta_t/1e6:.0f}ms. Packet id: {meas_packet.packet_id}"
            )
            if delta_t > 5e9 and delta_t < float("inf"):
                self._logger.warning(
                    f"Heading data and measurement packets synced with large time difference: {delta_t/1e9:.2f} seconds"
                )
            queue_put(self._queue_out, meas_packet, 0.1, logger=self._logger)

        except queue.Empty:
            pass
