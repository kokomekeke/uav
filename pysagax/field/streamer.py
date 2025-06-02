from queue import Queue
import queue
from typing import Any, Optional
from time import sleep, time

import zmq
from pysagax.communication.broadcast import TX

from pysagax.common.loop import Loop
import pysagax.message.command_pb2 as proto_cmd
from pysagax.message.data_types import DataType
import pysagax.message.data_pb2 as proto_data

import threading


class StreamerServer:
    """Background process for real-time bandwidth intensive UDP client communication"""

    def __init__(
        self, server: TX, level: int, timeout: int, telemetry_packet_period: int = 1
    ) -> None:
        self.server = server
        self.level = level
        self.timeout = timeout
        if telemetry_packet_period == 0:
            telemetry_packet_period = 1
        self.packet_period = {
            DataType.ERROR: 1,
            DataType.EVENT: 1,
            DataType.MEASUREMENT: 1,
            DataType.TELEMETRY: telemetry_packet_period,
        }


class Streamer(Loop):
    """
    Background process for sending stream packets to the clients.
    Sends each subscribed client the appropriate packets to their subscription levels.

    Levels:
    0, Heartbeat: Not yet implemented
    1, Telemetry: Only telemetry packets
    2, Detection: Measurement packets without amplitude spectrum and everything included in lower levels
    3, Spectrum: Measurement packets with amplitude spectrum  and everything included in lower levels

    TODO: Rethink levels:
        -Level for sending azimuth and elevation spectrums as well?
        -Is heartbeat needed?
        -Detection level should only stream measurement packets where the detection array is not empty?
            if so, there should be one more level for sending all measurement packets without spectrum data

    TODO: The cooperation between Streamer and StreamPreparation modules is poor.
        The functioning and efficiency could be greatly improved by redefining or merging them.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Set up command channel
        self._servers: dict[str, StreamerServer] = {}
        self._queue_in: Optional[Queue[Any]] = None
        self._conf_in: Optional[Queue[Any]] = None

        self._levels: dict[int, list[DataType]] = {
            0: [],  # TODO Heartbeat
            1: [DataType.TELEMETRY],  # Telemetry
            2: [
                DataType.TELEMETRY,
                DataType.EVENT,
                DataType.ERROR,
                DataType.MEASUREMENT,
            ],
            3: [
                DataType.TELEMETRY,
                DataType.EVENT,
                DataType.ERROR,
                DataType.MEASUREMENT,
            ],
        }
        self._known_intervals: dict[DataType, float] = {DataType.TELEMETRY: 0.25}
        self._total_packets: dict[DataType, int] = {
            DataType.TELEMETRY: 0,
            DataType.EVENT: 0,
            DataType.ERROR: 0,
            DataType.MEASUREMENT: 0,
        }

        self._latest_loop = time()
        self._restart_cnt = -1

    def __call__(
        self, queue_in: Queue[Any], conf_in: Queue[Any], *args, **kwargs
    ) -> None:
        self._queue_in = queue_in
        self._conf_in = conf_in
        return super()._call(*args, **kwargs)

    def _pre_loop(self) -> None:
        # Connect and bind communication ports
        pass

    def add_stream_client(self, target: proto_cmd.StreamTarget) -> None:
        try:
            if f"{target.address}:{target.port}" in self._servers:
                self.remove_stream_client(target)
            self._servers[f"{target.address}:{target.port}"] = StreamerServer(
                TX(target.address, port=target.port),
                int(target.level),
                0,
                target.telemetry_timeout,
            )
            self._servers[f"{target.address}:{target.port}"].server.connect()
            self._logger.info(f"Stream client {target.address}:{target.port} added")
        except zmq.ZMQError as zmqe:
            self._logger.error(f"ZMQError {zmqe.errno}: {str(zmqe)}")

    def remove_stream_client(self, target: proto_cmd.StreamTarget) -> None:
        try:
            self._servers[
                f"{target.address}:{target.port}"
            ].server.disconnect()  # TODO: handle key errorr
            del self._servers[f"{target.address}:{target.port}"]
            self._logger.info(f"Stream client {target.address}:{target.port} removed ")
        except KeyError:
            self._logger.critical(
                f"Trying to remove non-existent stream client '{target.address}:{target.port}' from stream client list [{self._servers.keys()}]"
            )

    def _loop(self) -> None:
        if time() - self._latest_loop > 2:
            # restart thread if no update for 2 seconds
            self._logger.critical(f"STREAM THREAD STOPPED AND RESTARTED")
            self._stream_thread = threading.Thread(target=self._stream_runner)
            self._stream_thread.daemon = True
            self._stream_thread.start()
            self._restart_cnt += 1
        self._logger.info(
            f"Streamer thread watcher: restarts_so_far= {self._restart_cnt}"
        )
        sleep(1)

    def _stream_runner(self):
        while True:
            self._latest_loop = time()
            self.stream_loop()

    def stream_loop(self) -> None:
        # Wait for response from Interpreter
        assert self._queue_in is not None
        assert self._conf_in is not None

        if self._handle_incoming_commands():
            # Early return if command arrived to check if there are more commands in the pipe
            return

        self._handle_single_data_packet()

    def _handle_incoming_commands(self):
        """
        Check for incoming command

        Returns True if a new command was received
        """
        try:
            command = self._conf_in.get(block=False)
            self._logger.debug("Got command packet")
            if isinstance(command, proto_cmd.Command):
                match command.instruction:
                    case proto_cmd.STREAM_START:
                        self.add_stream_client(command.target)
                    case proto_cmd.STREAM_STOP:
                        self.remove_stream_client(command.target)
                return True
        except queue.Empty:
            pass
        return False

    def _handle_single_data_packet(self):
        """Streams the incoming packets"""
        try:
            # TODO: On some devices (eg 10.1.1.114), at random times the process stops at Queue.get()
            # and never continues or raises an exception even though timeout is specified.
            #
            # I've worked around this bug by moving the main tasks into a thread
            # that is restarted if it doesn't loop anymore
            #
            # I didn't find any explanation to this behavior or any mention of this exact bug.
            # Possibly some sort of deadlock situation
            #
            # Might be worth it to report to bugs.python.org, but I couldn't make a
            #  more minimal reproducable code for it
            #
            # Possibly similar to: https://stackoverflow.com/a/59662879
            packet = self._queue_in.get(block=True, timeout=1)
            self._logger.debug(f"Got {type(packet).__name__} stream packet")

            # Serialize message
            stream_packet = packet.SerializeToString()
            if isinstance(packet, proto_data.Measurement):
                del packet.data[:]
                stream_packet_wo_spectrum = packet.SerializeToString()

            # Get type field (for streaming group string)
            type_field_enum = DataType.from_message(packet)
            if type_field_enum is None:
                self._logger.warning(
                    f"Cannot send packet type {type(packet).__name__} on Stream"
                )
                return
            type_field = DataType(type_field_enum)

            # Track sent package stats
            self._total_packets[type_field] += 1

            # Iterate over server objects for each subscriber
            for host_port, server in self._servers.items():
                if type_field not in self._levels[server.level] or (
                    server.packet_period[type_field] > 1
                    and (
                        self._total_packets[type_field]
                        % server.packet_period[type_field]
                        != 0
                    )
                ):
                    # Don't send if the stream level or the packet period criteria hasn't been met
                    self._logger.debug(
                        f"{packet.DESCRIPTOR.name} ({type_field.name} -> {type_field.value}) "
                        f"#{self._total_packets[type_field]} /{server.packet_period[type_field]}"
                        f" packet not sent to {host_port} level {server.level}"
                    )
                    continue

                self._logger.debug(
                    f"{packet.DESCRIPTOR.name} ({type_field.name} -> {type_field.value}) "
                    f"#{self._total_packets[type_field]} /{server.packet_period[type_field]}"
                    f" packet to {host_port} level {server.level} size {len(stream_packet)} bytes"
                )

                # stream the packet (with or without spectrum)
                if server.level == 2 and isinstance(packet, proto_data.Measurement):
                    server.server.send(stream_packet_wo_spectrum, type_field.value)
                else:
                    server.server.send(stream_packet, type_field.value)

        except queue.Empty:
            self._logger.debug(
                f"Streamer didn't receive packets for more than 1 second."
            )
        except zmq.ZMQError as zmqe:
            self._logger.error(f"ZMQError {zmqe.errno}: {str(zmqe)}")
        except BufferError as bufe:
            self._logger.error(f"Buffer error: {bufe}")
        except Exception as e:
            self._logger.critical(f"Streamer error {str(e)}")
