import multiprocessing
import queue
import threading
import time
from multiprocessing.managers import RemoteError
from typing import Callable, Optional

import pyvisa

from pysagax import CoreServicePacket, StreamConnectionProcess, BaseConnection


class DfResult:
    def __init__(self) -> None:
        self.level: float = 0
        self.df_level: float = 0
        self.azimuth: float = 0
        self.df_quality: float = 0
        self.no_signal: bool = False


class DfModule(threading.Thread):
    def __init__(
        self,
        df_callback: Callable[[DfResult], None],
        status_callback: Callable[[str], None],
    ) -> None:
        super().__init__(daemon=True)
        self.df_callback = df_callback
        self.status_callback = status_callback
        self.stop: bool = False

    def connect(self, connection_string: str) -> None:
        if ":" in connection_string:
            host_port_split = connection_string.split(":")
            host, port = (host_port_split[0], host_port_split[1])
            self._connect_ip(host, int(port))

    def set_freq(self, frequency: float) -> None:
        pass

    def set_bandwidth(self, bandwidth: float) -> None:
        pass

    def start_measurement(self) -> None:
        pass

    def stop_measurement(self) -> None:
        pass

    def _start_thread(self) -> None:
        self.start()

    def _stop_thread(self) -> None:
        self.stop = True
        pass

    def _loop(self) -> None:
        print("Base loop")
        time.sleep(0.5)

    def _connect_ip(self, host: str, port: int) -> None:
        pass

    def run(self) -> None:
        self.stop = False
        while not self.stop:
            self._loop()
        self.stop = False

    def disconnect(self) -> None:
        self.stop = True


class DDF260(DfModule):
    def __init__(
        self,
        df_callback: Callable[[DfResult], None],
        status_callback: Callable[[str], None],
    ) -> None:
        super().__init__(df_callback, status_callback)

        self.RD_TERMINATION = "\n"
        self.WR_TERMINATION = "\n"
        self.QUERY_DELAY = 0.3

        self.rm = pyvisa.ResourceManager()

        self.inst: Optional[pyvisa.resources.TCPIPSocket] = None
        print(self.rm.list_resources())

    def set_freq(self, frequency: float) -> None:
        assert self.inst is not None
        self.inst.write(f"FREQ {frequency:.0f}")

    def set_bandwidth(self, bandwidth: float) -> None:
        assert self.inst is not None
        self.inst.write(f"BAND {bandwidth:.0f}")

    def start_measurement(self) -> None:
        assert self.inst is not None
        # Activate DF sensor function
        self.inst.write('FUNC "AZIM","DFQ","DFL"')
        # Start measurement trace
        # Command: TRAC:FEED:CONT MTRACE,ALW
        self.inst.write("""TRAC:FEED:CONT MTRACE,ALW""")
        # Configure measurement time
        # Command: MEAS:DF:TIME <value> # in seconds
        # Note: <value> in seconds, e.g. 0.1 for 100 ms.
        self.inst.write("MEAS:DF:TIME MIN")
        self.inst.write("TRACE:FEED:CONT MTRACE, ALWays")  # CONT or PER
        self.inst.write("MEAS:DF:MODE OFF")  # CONT or PER
        self.inst.write("ROUT:GAIN ON")  # OFF, ON
        self.inst.write("ROUT:POL VERT")  # HOR , VERT
        self.inst.write("ROUT:RPAT 0")  # ant path, num, min or max
        self.inst.write("MEAS:MODE PER")  # PER or CONT
        self._start_thread()

    def _loop(self) -> None:
        assert self.inst is not None
        response = self.inst.query("TRAC? MTRACE")
        if response.strip() == "9.91E37":
            pass
        else:
            values = [float(val.strip()) for val in response.split(sep=",")]
            # Data format: <level>,<DF level>,<azimuth>,<DF Quality>
            result = DfResult()
            assert len(values) == 4
            result.level = values[0]
            result.df_level = values[1]
            result.azimuth = values[2]
            result.df_quality = values[3]
            self.df_callback(result)

    def _connect_ip(self, host: str, port: int) -> None:
        inst = self.rm.open_resource(
            resource_name=f"TCPIP::{host}::{port}::SOCKET", open_timeout=5000
        )
        assert isinstance(inst, pyvisa.resources.TCPIPSocket)
        self.inst = inst
        self.inst.read_termination = self.RD_TERMINATION
        self.inst.write_termination = self.WR_TERMINATION
        self.inst.query_delay = self.QUERY_DELAY
        print(self.inst.query("*IDN?"))


class LenaCommandThread(BaseConnection, threading.Thread):
    def __init__(self) -> None:
        super(LenaCommandThread, self).__init__()

    def receive_on_socket(self, data: bytes) -> None:
        """
        When text is received on the command socket, display it in the console textbox.
        """
        print(data.decode())

    def display_status(self, message: str) -> None:
        print(f"LENA Command Socket: {message}")

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.disconnect = False
        self.run_socket()


class LenaDf(DfModule):
    def __init__(
        self,
        df_callback: Callable[[DfResult], None],
        status_callback: Callable[[str], None],
    ) -> None:
        super().__init__(df_callback, status_callback)

        manager = multiprocessing.get_context("spawn").Manager()
        self.disconnect_value = manager.Value("i", 0)
        """
        Setting the '1' value of the disconnect_value multiprocessing variable will end the multiprocessing task on the
        next iteration.
        """
        self.packets_queue: multiprocessing.Queue[
            CoreServicePacket
        ] = multiprocessing.Queue()

        self.packet_handlers: dict[int, Callable[[CoreServicePacket], None]] = {
            1: self.handle_main,
            2: self.handle_dummy,
            3: self.handle_roi_result_packet,
            4: self.handle_roi_lost_packet,
            6: self.handle_dummy,
        }
        self.command_thread = LenaCommandThread()
        self.freq: float = 0
        self.bw: float = 0

        self.result_buffer = DfResult()
        self.result_buffer.no_signal = True

    def send_command(self, command: str) -> None:
        print(command)
        assert self.command_thread.client_socket is not None
        self.command_thread.client_socket.send(command.encode())

    def status_watcher_thread(
        self, status_queue: queue.Queue[str], stream_process: StreamConnectionProcess
    ) -> None:
        """
        Entry point of the watcher thread
        """
        while True:
            try:
                terminate = False
                self.disconnect_value.value = self.stop
                disp_message = ""
                while not status_queue.empty():
                    message = status_queue.get(
                        timeout=0.2
                    )  # get status message from stream process
                    if message == "END":
                        terminate = True
                    else:
                        disp_message = message
                if (
                    disp_message != ""
                ):  # only send the last message to UI (UI calls are slow)
                    self.status_callback(disp_message)
                if terminate:
                    self.command_thread.disconnect = True
                    stream_process.join()
                    stream_process.terminate()
                    return
            except queue.Empty:
                pass
            except BrokenPipeError:
                return
            except RuntimeError:
                return  # it might happen on the UI when closing the window
            except RemoteError:
                return

    def connect(self, connection_string: str) -> None:
        super().connect(connection_string)
        status_queue: multiprocessing.Queue[str] = multiprocessing.Queue()
        """
        The string elements of the status queue are the messages to be displayed on the GUI status bar
        """

        stream_process = StreamConnectionProcess(
            self.packets_queue, self.disconnect_value, status_queue
        )
        # The purpose of the watcher thread is to take the status messages from the multiprocessing process and display
        # them on the GUI, and to forward the disconnect signal to the process if the "Disconnect" button is clicked.
        watcher_thread = threading.Thread(
            target=self.status_watcher_thread,
            args=(status_queue, stream_process),
            daemon=True,
        )
        watcher_thread.start()

        """
        This queue will transfer the processed packets from the stream process to the main (GUI) process
        """
        stream_process.host_port = f"{connection_string}:12937"
        stream_process.start()
        self.command_thread.host_port = f"{connection_string}:12936"
        self.command_thread.start()
        self._start_thread()

    def handle_dummy(self, packet: CoreServicePacket) -> None:
        pass

    def handle_main(self, packet: CoreServicePacket) -> None:
        self.df_callback(self.result_buffer)

    def handle_roi_result_packet(self, packet: CoreServicePacket) -> None:
        self.result_buffer = DfResult()
        self.result_buffer.azimuth = packet.roi_azimuth

    def handle_roi_lost_packet(self, packet: CoreServicePacket) -> None:
        self.result_buffer = DfResult()
        self.result_buffer.no_signal = True

    def set_freq(self, frequency: float) -> None:
        self.freq = frequency

    def set_bandwidth(self, bandwidth: float) -> None:
        self.bw = bandwidth

    def start_measurement(self) -> None:
        super().start_measurement()
        self.send_command(
            f"SOURCE:Path! USRP MXI1Port1Dev1;"
            f"SOURCE:BurstStride! 32768;"
            f"SOURCE:ChannelGain! 0 60;"
            f"SOURCE:ChannelGain! 1 60;"
            f"SOURCE:ChannelGain! 2 60;"
            f"SOURCE:ChannelGain! 3 60;"
            f"SOURCE:CenterFrequency! {self.freq-5000:.0f};"
            f"SOURCE:IqRate! {self.bw:.0f};"
            f"SOURCE:Configure!;"
            f"AOA:BinCount! 4096;"
            f"AOA:Configure!;"
            f"SOURCE:Start!;"
            f"ROI:Enable! 1;"
            f"ROI:CenterFrequency! {self.freq};"
            f"ROI:Span! 2500;"
            f"ROI:Threshold! -150;"
            f"ROI:Configure!;"
        )

    def stop_measurement(self) -> None:
        super().stop_measurement()
        self.send_command(f"SOURCE:Stop!;")

    def _loop(self) -> None:
        try:
            packet: CoreServicePacket = self.packets_queue.get(
                timeout=0.5
            )  # get a packet from the stream process
            self.packet_handlers[packet.packet_type](packet)
        except queue.Empty:
            time.sleep(0.1)
            return

    def run(self) -> None:
        super().run()
