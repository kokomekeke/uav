import logging
import queue
import threading
import time
from queue import Queue
from typing import Any, Optional

import pysagax.message.heading_pb2 as proto_heading
from pysagax.common.loop import Loop
from pysagax.communication.pub_sub import SUB
from pysagax.communication.req_rep_tcp import REQ

from pysagax.util.queue_put import queue_put


class Heading(Loop):
    """Background process for communicating with the PySAGAX-Heading service"""

    def __init__(
        self,
        # TODO: Define useful defaults
        address: str = "127.0.0.1",
        port_control: int = 5566,
        port_stream: int = 5567,
        *args,
        **kwargs,
    ) -> None:
        Loop.__init__(self, *args, **kwargs)

        self._address = address
        self._port_control = port_control
        self._port_stream = port_stream
        # TODO: Set up control channel to CoreService here
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._queue_status: Optional[Queue] = None
        self._conn_control: Optional[REQ] = None
        self._conn_stream: Optional[SUB] = None
        self._last_status_update_time = 0.0

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        queue_status: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_in.put(proto_heading.HeadingConfig())
        self._queue_out = queue_out
        self._queue_status = queue_status
        self._logger.info(f"ZMQ REQ connecting to ZMQ REP on {self._address}:{self._port_control}")
        self._conn_control = REQ(self._address, self._port_control)
        self._logger.info(f"ZMQ SUB connecting to ZMQ PUB on {self._address}:{self._port_stream}")
        self._conn_stream = SUB(self._address, self._port_stream)

        return super()._call(*args, **kwargs)

    def display_status_callback(self, message: str) -> None:
        self._logger.info(message)

    def _pre_loop(self) -> None:
        self.disconnect = False
        assert self._conn_control and self._conn_stream
        self._conn_control.connect()
        self._conn_stream.connect()
        self._logger.info("Heading module is alive")

    def _loop(self) -> None:

        assert (
            self._queue_in is not None
            and self._queue_out is not None
            and self._queue_status is not None
        )
        assert self._conn_control and self._conn_stream
        if self._last_status_update_time + 5.0 < time.time():
            self._queue_in.put(proto_heading.HeadingConfig())  # Only to get status
        while True:
            try:
                command = self._queue_in.get_nowait()
                assert isinstance(command, proto_heading.HeadingConfig)
                response_raw = self._conn_control.send(command.SerializeToString())

                response = proto_heading.HeadingStatus()
                if response_raw is None:
                    self._logger.warning("No response for HeadingConfig")
                    return
                response.ParseFromString(response_raw)
                # self._logger.info(MessageToJson(response))
                self._last_status_update_time = time.time()
                queue_put(self._queue_status, response, 0.1, logger=self._logger)
            except queue.Empty:
                break
        heading_packet_raw = self._conn_stream.receive()
        if heading_packet_raw is not None:
            heading_packet = proto_heading.HeadingData()
            heading_packet.ParseFromString(heading_packet_raw)
            self._protobuf_to_log(heading_packet, level=logging.DEBUG)
            queue_put(self._queue_out, heading_packet, 0.1, logger=self._logger)
        else:
            self._logger.debug("No heading packet received")
