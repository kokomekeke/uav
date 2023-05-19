import math
import re
import threading
from typing import Optional

import numpy as np
import numpy.typing as npt
import serial


class CompassParser:
    def __init__(self) -> None:
        self.raw_values: Optional[npt.NDArray[np.float64]] = None
        """
        Raw coordinates received from compass sensor
        """
        self.values: Optional[npt.NDArray[np.float64]] = None
        """,
        Processed coordinates from compass sensor
        """
        self.angle: Optional[float] = None
        """
        Calculated compass angle
        """

    def parse(self, line: bytes) -> bool:
        return False


class SimpleParser(CompassParser):
    def __init__(self) -> None:
        super().__init__()
        self.pattern = re.compile(
            r"\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*"
        )
        """
        Regex pattern to find coordinates in serial data lines
        """
        self.mins: npt.NDArray[np.float64] = np.array([np.inf, np.inf, np.inf])
        """
        Minimum coordinate values, used for calibration
        """
        self.maxs: npt.NDArray[np.float64] = np.array([-np.inf, -np.inf, -np.inf])
        """
        Maximum coordinate values, used for calibration
        """

    def parse(self, line: bytes) -> bool:
        tokens = self.pattern.match(line.decode())
        if tokens is None:
            self.raw_values = None
            self.values = None
            self.angle = None
            return False
        try:
            self.raw_values = np.array(
                [
                    float(tokens.group(4)),
                    float(tokens.group(5)),
                    float(tokens.group(6)),
                ]
            )
            self.mins = np.array(
                [min(mini, raw) for mini, raw in zip(self.mins, self.raw_values)]
            )
            self.maxs = np.array(
                [max(maxi, raw) for maxi, raw in zip(self.maxs, self.raw_values)]
            )
            self.values = np.array(
                [
                    raw - ((mini + maxi) / 2)
                    for mini, maxi, raw in zip(self.mins, self.maxs, self.raw_values)
                ]
            )
            self.angle = math.atan2(self.values[0], self.values[1])
            return True
        except ValueError:
            self.raw_values = None
            self.values = None
            self.angle = None
            return False


class AaroniaParser(CompassParser):
    def __init__(self) -> None:
        super().__init__()
        self.pattern = re.compile(
            r"\$PAAG,DATA,(.),(\d{6})\.(\d*),([-\d.]*),([-\d.]*),([-\d.]*),(.)\*([0-9A-F]{2})"
        )

    def parse(self, line: bytes) -> bool:
        line = line.strip()
        if not (line[0] == ord("$") and line[-3] == ord("*")):
            return False
        data_checksum = line[-2:]
        char_check = 0
        for char in line[1:-3]:
            char_check ^= char
        if f"{char_check:02X}".encode() != data_checksum:
            return False
        tokens = self.pattern.match(line.decode())
        if tokens is None:
            return False
        if tokens is not None:
            data_type = tokens[1]
            data_hms = (int(tokens[2][0:2]), int(tokens[2][2:4]), int(tokens[2][4:6]))
            data_timestamp = data_hms[0] * 3600 + data_hms[1] * 60 + data_hms[2]
            data_idx = int(tokens[3])
            data_coord = (float(tokens[4]), float(tokens[5]), float(tokens[6]))
            data_ok = tokens[7]
            if data_ok == "A" and data_type == "C":
                self.raw_values = np.array(data_coord)
                self.values = np.array(
                    [data_coord[0] / 1090, data_coord[1] / 1090, data_coord[2] / 1090]
                )
                self.angle = math.atan2(data_coord[1], data_coord[0])
                return True
            return False


class CompassSensor(threading.Thread):
    def __init__(self, sensor_dev: serial.Serial, parser: CompassParser) -> None:
        super().__init__()
        self.daemon = True
        self.ser: serial.Serial = sensor_dev  # serial.Serial()

        self.sensor: float = 0.0
        self.compass = np.array([0.0, 0.0, 0.0])

        self.addr = None

        self.parser: CompassParser = parser

    def run(self) -> None:
        pattern = re.compile(
            r"\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*"
        )
        while True:
            try:
                line = self.ser.readline()
                if self.parser.parse(line):
                    assert self.parser.raw_values is not None
                    assert self.parser.angle is not None
                    self.compass = self.parser.raw_values
                    self.sensor = self.parser.angle
            except Exception as e:
                print(e)

    def close(self) -> None:
        self.ser.close()


def open_arduino_serial_dev(device_string: str) -> serial.Serial:
    ser = serial.Serial()
    ser.port = device_string  # "/dev/rfcomm2"
    # If it breaks try the below
    # self.serConf() # Uncomment lines here till it works

    ser.baudrate = 9600
    ser.bytesize = serial.EIGHTBITS
    ser.parity = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.timeout = 50  # Non-Block reading
    ser.xonxoff = False  # Disable Software Flow Control
    ser.rtscts = False  # Disable (RTS/CTS) flow Control
    ser.dsrdtr = False  # Disable (DSR/DTR) flow Control
    # self.ser.writeTimeout = 2
    ser.open()
    # self.ser.flushInput()
    # self.ser.flushOutput()
    return ser


def open_aaronia_serial_dev() -> serial.Serial:
    from pyftdi.ftdi import Ftdi  # type: ignore

    try:
        Ftdi.add_custom_vendor(0x0403)
    except Exception as e:
        print(e)
    try:
        Ftdi.add_custom_product(0x0403, 0xE8DB)
    except Exception as e:
        print(e)
    import pyftdi.serialext  # type: ignore

    return pyftdi.serialext.serial_for_url("ftdi://ftdi:0xe8db/1", baudrate=625000)  # type: ignore
