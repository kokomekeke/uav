import multiprocessing
import queue
import typing

from pysagax import CoreServicePacket, CoreServiceParser, BaseConnection


class StreamAndCompassProcess(
    CoreServiceParser, BaseConnection, multiprocessing.Process
):
    def __init__(
        self,
        queues: typing.Iterable[queue.Queue[tuple[float, CoreServicePacket]]],
        disconnect_value: multiprocessing.managers.ValueProxy[int],
        status_value: queue.Queue[str],
    ):
        CoreServiceParser.__init__(self)
        BaseConnection.__init__(self)
        multiprocessing.Process.__init__(self)
        self.queues = queues

        self.packet_count = 0
        """
        Overall packet count
        """

        self.mp_status: queue.Queue[str] = status_value
        """
        Status message queue for multiprocessing process
        """

        self.mp_disconnect: multiprocessing.managers.ValueProxy[int] = disconnect_value
        """
        Disconnect signal for multiprocessing process
        """

    def receive_on_socket(self, data: bytes) -> None:
        """
        When data is received on the socket, this function will construct a packet object from the binary data.
        """
        for cs_packet in self.extract_packets(data):
            cs_packet.packet_index = self.packet_count
            self.packet_count += 1
            for queue in self.queues:
                queue.put((0.123, cs_packet))

    def run(self) -> None:
        """
        Entry point of the stream collecting process.
        """
        self.run_socket()
        self.mp_status.put("END")

    def is_disconnect(self) -> bool:
        """
        Returns: if the socket should manually disconnect
        """
        assert self.mp_disconnect is not None
        return bool(self.mp_disconnect.value)

    def display_status(self, message: str) -> None:
        """
        Display a status message (on the GUI status bar)
        """
        assert self.mp_status
        print(f"[StreamAndCompassProcess] {message}")
        self.mp_status.put(message)
