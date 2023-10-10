import multiprocessing
import queue
import re
import threading
import traceback
import typing
from typing import Optional

import serial

import pysagax
from pysagax import (
    CoreServicePacket,
    CoreServiceParser,
    BaseConnection,
    CompassSensor,
)

"""
Class for handling multiple multiprocessing.Queue objects together.
It could be modified to take queue.Queue objects as well. 
"""
class MultiQueue():
    def __init__(self, queues = []):
        manager = multiprocessing.get_context("spawn").Manager()
        self.queues = manager.dict()
        for queue in queues:
            self.add_queue(queue)

    def add_queue(self, queue: multiprocessing.Queue):
        """
        Add a queue
        """
        if not isinstance(queue, multiprocessing.managers.BaseProxy):
            raise ValueError("Input must be a multiprocessing.managers.Queue object")
        self.queues[id(queue)] = queue

    def remove_queue(self, queue):
        """
        Remove a queue by reference
        """
        if self.queues.pop(id(queue), None) is None:
            raise ValueError("Queue not found in MultiQueue")

    def put(self, item, block=True, timeout=None):
        """
        Put an item into all queues
        """
        ##TODO: properly handle if one of the queues is full
        for q in self.queues.values():
            try:
                q.put(item, block=False)
            except multiprocessing.queues.Full:
                pass #we ignore full queues for now, since multiprocessing queues can't be used similarly to collections.Deque objects or be cleared easily.

    def empty(self):
        """
        Check if the every queue in MultiQueue is empty.
        """
        if not self.queues:
            raise ValueError("No queues added to MultiQueue")
        return all(queue.empty() for queue in self.queues)
    

class EncoderThread(threading.Thread):  ###
    def __init__(self, port: str, status_queue: queue.Queue[str]):
        super().__init__()
        self.daemon = True
        self.port = port
        self.angle = float("NaN")
        self.connection = None
        self.status_queue = status_queue

    def run(self):
        global run_threads
        try:
            self.connection = serial.Serial(self.port, baudrate=9600, timeout=0.5)
            self.status_queue.put("#encoder" + "Connected")
        except:
            self.status_queue.put("#encoder" + f"Could not connect to encoder on port {self.port}")
            return
        while True: ##TODO: stop condition and connection closing
            try:
                msg = self.connection.readline()
                ctr = re.findall(r"\d+\.\d+", str(msg))
                if len(ctr):
                    self.angle = pysagax.normalize_angle(float(ctr[0]))
            except:
                self.angle = float("NaN")
                self.status_queue("#encoder" + "Disconnected.")
                break
        self.close()
    def close(self):
        if self.connection is not None:
            self.connection.close()

class StreamAndCompassProcess(
    CoreServiceParser, BaseConnection, multiprocessing.Process
):
    def __init__(
        self,
        queues: MultiQueue,
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

        self.compass_host_port: Optional[str] = None

        self.encoder_port: Optional[str] = None

        self.compass = None

        self.encoder = None

        self.compass_offset = 0.0

        self.encoder_offset = 0.0

    def receive_on_socket(self, data: bytes) -> None:
        """
        When data is received on the socket, this function will construct a packet object from the binary data.
        """
        for cs_packet in self.extract_packets(data):
            cs_packet.packet_index = self.packet_count
            self.packet_count += 1

            compass_heading = pysagax.normalize_angle(self.compass.angle - self.compass_offset) if self.compass is not None else None
            encoder_heading = pysagax.normalize_angle(self.encoder.angle - self.encoder_offset) if self.encoder is not None else None

            data = {"cs_packet": cs_packet,
                    "compass_angle": self.compass.angle if self.compass is not None else None,
                    "compass_heading": compass_heading,
                    "encoder_angle": self.encoder.angle if self.encoder is not None else None,
                    "encoder_heading": encoder_heading,
                    }
            
            self.queues.put(data)

    def run(self) -> None:
        """
        Entry point of the stream collecting process.
        """        
        self.init_compass_thread()
        
        self.init_encoder_thread()

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
        self.mp_status.put(message)

    def init_compass_thread(self):
                
        self.compass = CompassSensor(pysagax.AaroniaParser())
        #TODO: put CompassSensor errors in status queue instead of messagebox and print
        try:
            self.compass.load_calibration()
        except FileNotFoundError:
            self.mp_status.put("#compass" + "Startup error, Calibration file calibration.npz not found. Make sure sgx-pc is your workdir")
            # messagebox.showerror( ##TODO
            #     "Startup error",
            #     "Calibration file calibration.npz not found. Make sure sgx-pc is your workdir.",
            # )

        try:
            self.compass.set_serial_device(
                pysagax.open_aaronia_socket_dev(self.compass_host_port)
            )
        except serial.SerialException:
            self.mp_status("#compass" + "Compass sensor not connected")
        except ConnectionError as e:
            self.mp_status.put("#compass" + str(e))
            self.compass = None
            return
        else:
            self.mp_status.put("#compass" + "Connected")
        self.compass.start()

    def init_encoder_thread(self):        
        self.encoder = EncoderThread(self.encoder_port, self.mp_status)
        self.encoder.start()

