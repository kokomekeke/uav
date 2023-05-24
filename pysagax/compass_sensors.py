import math
import re
import threading
import time
from typing import Optional

import numpy as np
import numpy.typing as npt
import serial


class CompassParser:
    def __init__(self) -> None:
        self.raw_magnetometer_values: Optional[npt.NDArray[np.float64]] = None
        """
        Raw coordinates received from magnetometer sensor
        """
        self.raw_accelerometer_values: Optional[npt.NDArray[np.float64]] = None
        """
        Raw coordinates coordinates from accelerometer sensor (if present)
        """
        self.raw_gyroscope_values: Optional[npt.NDArray[np.float64]] = None
        """
        Raw coordinates coordinates from gyroscope sensor (if present)
        """
        self.magnetometer_values: Optional[npt.NDArray[np.float64]] = None
        """
        Processed coordinates from magnetometer sensor
        """
        self.accelerometer_values: Optional[npt.NDArray[np.float64]] = None
        """
        Processed coordinates from accelerometer sensor (if present)
        """
        self.gyroscope_values: Optional[npt.NDArray[np.float64]] = None
        """
        Processed coordinates from gyroscope sensor (if present)
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
            self.raw_magnetometer_values = None
            self.magnetometer_values = None
            self.angle = None
            return False
        try:
            self.raw_magnetometer_values = np.array(
                [
                    float(tokens.group(4)),
                    float(tokens.group(5)),
                    float(tokens.group(6)),
                ]
            )
            self.raw_accelerometer_values = np.array(
                [
                    float(tokens.group(1)),
                    float(tokens.group(2)),
                    float(tokens.group(3)),
                ]
            )
            self.mins = np.array(
                [
                    min(mini, raw)
                    for mini, raw in zip(self.mins, self.raw_magnetometer_values)
                ]
            )
            self.maxs = np.array(
                [
                    max(maxi, raw)
                    for maxi, raw in zip(self.maxs, self.raw_magnetometer_values)
                ]
            )
            self.magnetometer_values = np.array(
                [
                    raw - ((mini + maxi) / 2)
                    for mini, maxi, raw in zip(
                        self.mins, self.maxs, self.raw_magnetometer_values
                    )
                ]
            )
            self.angle = math.atan2(
                float(self.magnetometer_values[0]), float(self.magnetometer_values[1])
            )
            return True
        except ValueError:
            self.raw_magnetometer_values = None
            self.magnetometer_values = None
            self.angle = None
            return False


class AaroniaParser(CompassParser):
    def __init__(self) -> None:
        super().__init__()
        self.is_new: tuple[bool, bool, bool] = (False, False, False)
        self.pattern = re.compile(
            r"\$PAAG,DATA,(.),(\d{6})\.(\d*),([-\d.]*),([-\d.]*),([-\d.]*),(.)\*([0-9A-F]{2})"
        )

    def parse(self, line: bytes) -> bool:
        line = line.strip()
        if len(line) < 3:
            return False
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
            # Aaronia Raw data processing, see
            # https://dev.aaronia-shop.com/downloads/gps/manuals/gps_logger_programming_guide_en.pdf
            if data_ok == "A":
                if data_type == "C":
                    scalar = 100000.0 / 1090.0  # nanotesla
                    self.raw_magnetometer_values = np.array(data_coord)
                    self.magnetometer_values = np.array(
                        [
                            data_coord[0] * scalar,
                            data_coord[1] * scalar,
                            data_coord[2] * scalar,
                        ]
                    )
                    self.angle = math.atan2(data_coord[1], data_coord[0])
                    self.is_new = (True, self.is_new[1], self.is_new[2])
                if data_type == "G":
                    self.raw_gyroscope_values = np.array(data_coord)
                    scalar = np.pi / (180.0 * 14.375)
                    self.gyroscope_values = np.array(
                        [
                            data_coord[0] * scalar,
                            data_coord[1] * scalar,
                            data_coord[2] * scalar,
                        ]
                    )
                    self.is_new = (self.is_new[0], True, self.is_new[2])
                if data_type == "T":
                    self.raw_accelerometer_values = np.array(data_coord)
                    scalar = 9.80665 / 8192.0  # Range is -2g..2g
                    self.accelerometer_values = np.array(
                        [
                            data_coord[0] * scalar,
                            data_coord[1] * scalar,
                            data_coord[2] * scalar,
                        ]
                    )
                    # d_pi = 180.0 / np.pi
                    # accelerometer_rotation = np.array(
                    #     [
                    #         -math.atan2(y, math.sqrt((x * x) + (z * z))) * d_pi,
                    #         math.atan2(-x, (-1 if z < 0 else 1) * math.sqrt((y * y) + (z * z))) * d_pi,
                    #         0
                    #     ]
                    # )
                    self.is_new = (self.is_new[0], self.is_new[1], True)
                if all(self.is_new):
                    self.is_new = (False, False, False)
                    return True
            return False


class CompassSensor(threading.Thread):
    def __init__(self, sensor_dev: serial.Serial, parser: CompassParser) -> None:
        super().__init__()
        self.daemon = True
        self.ser: serial.Serial = sensor_dev  # serial.Serial()

        self.angle: float = 0.0
        self.yaw: float = 0.0
        self.pitch: float = 0.0
        self.roll: float = 0.0
        self.heading = np.array([0.0, 0.0, 0.0])

        self.addr = None

        self.parser: CompassParser = parser

        import ahrs

        self.ahrs_filter = ahrs.filters.EKF()
        self.ahrs_filter.Dt = 0.1
        self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])

    def run(self) -> None:
        pattern = re.compile(
            r"\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*"
        )
        previous_time = time.time()
        while True:
            line = b""
            try:
                line = self.ser.readline()
            except Exception as e:
                print(e)
            if self.parser.parse(line):
                current_time = time.time()
                self.ahrs_filter.Dt = current_time - previous_time
                self.quaternion = self.ahrs_filter.update(
                    q=self.quaternion,
                    gyr=self.parser.gyroscope_values,
                    acc=self.parser.accelerometer_values,
                    mag=self.parser.magnetometer_values,
                )
                previous_time = current_time
                self.heading = self.quaternion[1:4]
                self.calculate_angle()
                self.angle = self.yaw
                print(self.quaternion)

    def calculate_angle(self) -> None:
        w, x, y, z = (
            self.quaternion[0],
            self.quaternion[1],
            self.quaternion[2],
            self.quaternion[3],
        )
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        self.roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = math.sqrt(1 + 2 * (w * y - x * z))
        cosp = math.sqrt(1 - 2 * (w * y - x * z))
        self.pitch = 2 * math.atan2(sinp, cosp) - np.pi / 2

        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        self.yaw = math.atan2(siny_cosp, cosy_cosp)

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
    Ftdi.show_devices()
    import pyftdi.serialext  # type: ignore

    aaronia: serial.Serial = pyftdi.serialext.serial_for_url(
        "ftdi://ftdi:0xe8db/1", baudrate=625000
    )
    aaronia.write(b"$PAAG,MODE,START\r\n")
    return aaronia
