import logging
from queue import Queue, Empty
from typing import Any, Optional
from time import sleep, time

import queue
from pysagax.common.loop import Loop

from pysagax.util.queue_put import queue_put

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.altiss_intra_uav_pb2 as proto_altiss


class APMMessenger(Loop):
    """
    Creates and forwards messages to the Avionics Processing Module (APM) of the Altiss project.

    Currently it handles the forwarding of emitter geolocation data.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._queue_in: Optional[Queue] = None
        self._command_q: Optional[Queue] = None
        self._response_q: Optional[Queue] = None

        self._message_frequency = 1
        self._last_packet_sent = time()

        self._latest_geolocations = {}

    def __call__(
            self, queue_in: Queue[Any], cmd_queue: Queue[Any], rsp_queue: Queue[Any], *args, **kwargs
    ) -> None:
        self._queue_in = queue_in
        self._command_q = cmd_queue
        self._response_q = rsp_queue

        return super()._call(*args, **kwargs)

    def _get_new_data(self):
        # get message from input queue
        try:
            roi, timestamp, lat, lon = self._queue_in.get(timeout=1)
        except Empty:  # no message arrived
            return

        self._latest_geolocations[roi] = proto_altiss.EmitterData(
            timestamp_unix=int(timestamp.timestamp() * 1e6),
            latitude=lat,
            longitude=lon,
            altitude=0,
        )

    def _send_to_apm(self):
        """
        Returns None if nothing to send. Else it returns a response.
        """
        # send acqured data then delete the geoloc dict so we dont send non updated data again
        # cutoff_time = current_time - self._message_frequency
        # for roi, emitter_data in self._latest_geolocations.items():
        # if emitter_data.timestamp_unix * 1e6 < self._last_packet_sent - self._message_frequency:
        if not self._latest_geolocations:
            # don't send empty packet
            self._logger.info("No geolocation data to be sent to APM")
            return None

        cmd = proto_cmd.Command(
            instruction=proto_cmd.FORWARD_TO_APM,
            msg_to_apm=proto_cmd.MessageToAPM(
                emitter_events=proto_altiss.ComIntEmitterEvents())
        )
        cmd.msg_to_apm.emitter_events.timestamp.GetCurrentTime()
        cmd.msg_to_apm.emitter_events.emitter_data.extend(
            self._latest_geolocations.values()
        )
        self._logger.trace(f"Data sent to Commagregate {cmd}")

        target_uav_id = 0  # Forward to all connected UAVs
        # TODO: should we not forward to all UAVs?

        try:
            self._command_q.put((target_uav_id, cmd), timeout=2)
        except Exception as e:
            response = proto_cmd.Response(success=False)
            response.error.description = f"Cant forward message to Commagregate: {e}"
            return response

        self._latest_geolocations = {}
        try:
            response = self._response_q.get(timeout=self._message_frequency / 2)
        except queue.Empty:
            response = proto_cmd.Response(success=False)
            response.error.description = f"No response for APM forward command"
        return response

    def _loop(self) -> None:
        # get message from input queue
        self._get_new_data()

        current_time = time()
        if current_time > self._last_packet_sent + self._message_frequency:
            response = self._send_to_apm()
            self._last_packet_sent = current_time
            if response is None:
                return
            if not response.success:
                self._logger.critical(response.error.description)

