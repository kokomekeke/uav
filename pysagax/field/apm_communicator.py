import logging
from queue import Queue, Empty
from typing import Any, Optional
from time import sleep

from pysagax.common.loop import Loop

import zmq

from pysagax.util.queue_put import queue_put
from pysagax.util.run_once import run_once

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.altiss_intra_uav_pb2 as proto_altiss


# dict mapping packet types to their respective PUB/SUB topics used on board of the UAV
PACKET_TYPE_TOPICS = {
    proto_altiss.ComIntEmitterEvents: b"cee",
}


class APMCommunicator(Loop):
    """
    Handles communication with the Avionics Processing Module (APM) of the Altiss project.

    For example, this process is responsible for streaming the calculated geolocation data of detected emitters
    """

    def __init__(self, apm_address, *args, **kwargs) -> None:
        """
        apm_address: string of ip and port of APM module

        TODO: If apm_address is None, the APMCommunicator shuts down (or it shouldn't even be made by Commander)
        """
        super().__init__(*args, **kwargs)

        # Set up command channel
        self._server: Optional[zmq.SyncSocket] = None
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None

        self._apm_address = apm_address

    def __call__(
        self, queue_in: Queue[Any], queue_out: Queue[Any], *args, **kwargs
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out

        return super()._call(*args, **kwargs)

    def _publish_msg(self, message) -> proto_cmd.Response:
        """
        Publish message with the appropriate topic based on its type.

        Returns a Response with error and success fields filled.
        """
        # TODO: do not overload APM with messages
        #       eg only 1 ComIntEmitterEvents packet / emitter / second
        try:
            topic = PACKET_TYPE_TOPICS[type(message)]
        except KeyError:
            response = proto_cmd.Response(success=False)
            response.error.description = f"Unknown message type {type(message)}"
            self._logger.warning(response.error.description)
            return response

        self._logger.trace(f"publishing message with topic: {topic}")
        self._server.send_multipart([topic, message.SerializeToString()])
        return proto_cmd.Response(success=True)

    def _pre_loop(self) -> None:
        if self._apm_address is None:
            self._logger.warning(f"APM address not provided. Publish socket not opened")
            return

        # creating zmq PUB socket
        context = zmq.Context()
        self._server = context.socket(zmq.PUB)

        address = f"tcp://{self._apm_address}"
        self._server.connect(address)

        self._logger.info(f"PUB socket live on {address}")

    def _loop(self) -> None:
        # get message from input queue
        try:
            msg: proto_cmd.Command = self._queue_in.get(timeout=1)
        except Empty:  # no message arrived
            sleep(0.1)
            return

        if self._apm_address is None:
            # No APM -> drop the packet
            response = proto_cmd.Response(success=False)
            response.error.description = "Packet can't be forwarded to APM since its address wasn't provided at launch"
            self._log_no_apm_socket_opened()
        else:
            # remove payload from ToAPM message
            payload = getattr(msg.msg_to_apm, msg.msg_to_apm.WhichOneof("payload"))

            # publish payload
            response = self._publish_msg(message=payload)

        # send a response in a queue
        queue_put(self._queue_out, response, timeout=0.5)

    @run_once(timeout=20)
    def _log_no_apm_socket_opened(self):
        self._logger.error(
            "Packet can't be forwarded to APM since its address wasn't provided at launch"
        )
