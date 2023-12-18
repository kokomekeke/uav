import queue
import re
import threading

import serial

import pysagax


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
            self.status_queue.put(
                "#encoder" + f"Could not connect to encoder on port {self.port}"
            )
            return
        while True:  ##TODO: stop condition and connection closing
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
