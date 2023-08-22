import io
import math
import re
import socket
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

import ahrs  # type: ignore
import numpy as np
import numpy.typing as npt
import scipy  # type: ignore
import serial
from pysagax.magnetometer_calibration import MagnetometerCalibration
from tkinter import messagebox


class CompassParser:
    """
    Base class for compass sensor hardware handler driver
    """

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

    def parse(self, line: bytes) -> bool:
        return False


class SimpleParser(CompassParser):
    """
    The parser driver class for arduino compass sensors.
    """

    def __init__(self) -> None:
        super().__init__()
        self.pattern = re.compile(
            r"\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*"
        )

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
            self.magnetometer_values = self.raw_magnetometer_values
            self.raw_accelerometer_values = np.array(
                [
                    float(tokens.group(1)),
                    float(tokens.group(2)),
                    float(tokens.group(3)),
                ]
            )
            self.accelerometer_values = self.raw_accelerometer_values
            return True
        except ValueError:
            self.raw_magnetometer_values = None
            self.magnetometer_values = None
            return False


class AaroniaParser(CompassParser):
    """
    Parser driver class for the Aaronia AG GPS Data Logger sensor
    """

    def __init__(self) -> None:
        super().__init__()
        self.is_new: tuple[bool, bool, bool] = (False, False, False)
        """
        A sample is processed when all three sensors have new data.
        """

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
            data_hms = (
                int(tokens[2][0:2]),
                int(tokens[2][2:4]),
                int(tokens[2][4:6]),
            )  # original timestamp is HHMMSS format
            data_timestamp = (
                data_hms[0] * 3600 + data_hms[1] * 60 + data_hms[2]
            )  # Timestamp is converted to total seconds
            data_idx = int(tokens[3])
            data_coord = (float(tokens[4]), float(tokens[5]), float(tokens[6]))
            data_ok = tokens[7]
            # Aaronia Raw data processing, see
            # https://dev.aaronia-shop.com/downloads/gps/manuals/gps_logger_programming_guide_en.pdf
            if data_ok == "A":
                if data_type == "C":
                    scalar = 100000.0 / 1090.0  # -> nanotesla
                    self.raw_magnetometer_values = np.array(data_coord)
                    self.magnetometer_values = np.array(
                        [
                            data_coord[0] * scalar,
                            data_coord[1] * scalar,
                            data_coord[2] * scalar,
                        ]
                    )
                    self.angle = math.atan2(data_coord[1], data_coord[0])  # not used
                    self.is_new = (True, self.is_new[1], self.is_new[2])
                if data_type == "G":
                    self.raw_gyroscope_values = np.array(data_coord)
                    scalar = np.pi / (180.0 * 14.375 * 7)  # -> radians / sec
                    self.gyroscope_values = np.array(
                        [
                            data_coord[0] * scalar,
                            data_coord[1] * scalar,
                            data_coord[2] * scalar,
                        ]
                    )
                    self.is_new = (self.is_new[0], True, self.is_new[2])
                if data_type == "T":
                    self.raw_accelerometer_values = np.array(
                        data_coord
                    )  # Range is -2g..2g
                    scalar = 9.80665 / 8192.0  # -> m/s^2
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


class CalibrationStatus(Enum):
    NONE = 0
    CALIBRATING = 1
    CALIBRATED = 2
    ACTION_REQUIRED = 3


class Calibration:
    def __init__(
        self,
        get_sample: Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]],
        do_calibration: Callable[[npt.NDArray[np.float64]], None],
    ):
        self.status: CalibrationStatus = CalibrationStatus.NONE
        self.calibration_dataset: npt.NDArray[np.float64] = np.empty([0, 3])
        """
        The samples that are used to calibrate the sensor
        """

        self.do_calibration: Callable[[npt.NDArray[np.float64]], None] = do_calibration
        """
        A function that calculates the calibration parameters based on the calibration dataset.
        """

        self.get_sample: Callable[
            [npt.NDArray[np.float64]], npt.NDArray[np.float64]
        ] = get_sample
        """
        A function that converts an uncalibrated sample to a calibrated one
        """

        self.calibration_instructions = ""
        """
        A message that tells how the calibration should be performed.
        """

    def s(self, vec: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Calculates a calibrated sample from an uncalibrated one if sensor is calibrated.
        """
        if self.status == CalibrationStatus.CALIBRATING:
            self.calibration_dataset = np.append(
                self.calibration_dataset,
                np.array([vec]),
                axis=0,
            )
            return vec
        elif self.status == CalibrationStatus.CALIBRATED:
            return self.get_sample(vec)
        else:
            return vec

    def begin_calibration(self) -> None:
        """
        Begins the calibration data collection phase.
        """
        self.calibration_dataset = np.empty([0, 3])
        self.status = CalibrationStatus.CALIBRATING

    def end_calibration(self) -> None:
        """
        Ends the calibration data collection phase and does the calibration parameter calculation.
        """
        self.do_calibration(self.calibration_dataset)
        self.status = CalibrationStatus.CALIBRATED

    def __str__(self) -> str:
        return [
            "Not calibrated",
            f"Calibrating... ({self.calibration_dataset.shape[0]} samples) {self.calibration_instructions}",
            "Calibrated",
            f"{self.calibration_instructions}",
        ][self.status.value]


class GyroCalibration(Calibration):
    def __init__(self) -> None:
        super().__init__(self.do_sample, self.do_calibrate)
        self.gyro_offsets = np.zeros([3])
        self.gyro_max_variance = np.zeros([3])
        self.gyro_beta = 0.0
        """
        Beta is the parameter of the AHRS filter.
        """
        self.calibration_instructions = "Hold the sensor still on a horizontal surface"

    def do_calibrate(self, ds: npt.NDArray[np.float64]) -> None:
        for i in range(
            0, 3
        ):  # https://makersportal.com/blog/calibration-of-an-inertial-measurement-unit-imu-with-raspberry-pi-part-ii
            self.gyro_offsets[i] = np.mean(np.array(ds)[:, i])
            self.gyro_max_variance[i] = np.max(
                np.array(ds)[:, i] - self.gyro_offsets[i]
            )
        print(f"Gyro offsets: {self.gyro_offsets}")
        print(f"Gyro error: {self.gyro_max_variance}")
        self.gyro_beta = float(np.max(self.gyro_max_variance) * 3)

    def do_sample(self, vec: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return vec - self.gyro_offsets


class AccelCalibration(Calibration, threading.Thread):
    def __init__(self) -> None:
        threading.Thread.__init__(self)
        self.daemon = True
        super().__init__(self.do_sample, self.do_calibrate)
        self.gyro_offsets = np.zeros([3])
        self.gyro_max_variance = np.zeros([3])
        self.gyro_beta = 0.0
        """
        Beta is the parameter of the AHRS filter.
        """
        self.calibration_instructions = "Hold the sensor still on a horizontal surface"

        self.mpu_offsets: list[list[float]] = [[], [], []]  # offset array to be printed

    def accel_fit(self, x_input: float, m_x: float, b: float) -> float:
        return (m_x * x_input) + b  # fit equation for accel calibration

    def run(self) -> None:
        super().run()
        cal_size = 100
        axis_vec = ["z", "y", "x"]  # axis labels
        cal_directions = [
            "upward",
            "downward",
            "perpendicular to gravity",
        ]  # direction for IMU cal
        cal_indices = [2, 1, 0]  # axis indices
        for axis_index, axis_label in enumerate(axis_vec):
            ax_offsets: list[list[float]] = [[], [], []]
            print("-" * 50)
            for dir_index, dir_label in enumerate(cal_directions):
                self.calibration_instructions = (
                    f"Keep IMU Steady with the {axis_label}-axis pointed {dir_label}"
                )
                self.status = CalibrationStatus.ACTION_REQUIRED
                while self.status == CalibrationStatus.ACTION_REQUIRED:
                    time.sleep(0.1)
                self.calibration_instructions = f"Calibrating, keep IMU Steady with the {axis_label}-axis pointed {dir_label}"
                self.calibration_dataset = np.empty([0, 3])
                while self.calibration_dataset.shape[0] < cal_size:
                    time.sleep(0.1)
                ax_offsets[dir_index] = list(
                    np.array(self.calibration_dataset)[:, cal_indices[axis_index]]
                )  # offsets for direction

            # Use three calibrations (+1g, -1g, 0g) for linear fit
            popts = scipy.optimize.curve_fit(
                self.accel_fit,
                np.append(np.append(ax_offsets[0], ax_offsets[1]), ax_offsets[2]),
                np.append(
                    np.append(
                        1.0 * np.ones(np.shape(ax_offsets[0])),  # type: ignore
                        -1.0 * np.ones(np.shape(ax_offsets[1])),  # type: ignore
                    ),
                    0.0 * np.ones(np.shape(ax_offsets[2])),  # type: ignore
                ),
                maxfev=10000,
            )
            self.mpu_offsets[cal_indices[axis_index]] = popts[
                0
            ]  # place slope and intercept in offset array
        print("Accelerometer Calibrations Complete")
        print(self.mpu_offsets)
        self.status = CalibrationStatus.CALIBRATED

    def do_calibrate(self, ds: npt.NDArray[np.float64]) -> None:
        pass

    def do_sample(self, vec: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return np.array(
            [
                float(
                    self.accel_fit(
                        vec[ax], self.mpu_offsets[ax][0], self.mpu_offsets[ax][1]
                    )
                )
                * ahrs.MEAN_NORMAL_GRAVITY
                for ax in range(3)
            ]
        )

    def next_calibration_step(self) -> None:
        if (
            self.status == CalibrationStatus.NONE
            or self.status == CalibrationStatus.CALIBRATED
        ):
            self.status = CalibrationStatus.ACTION_REQUIRED
            self.start()
        elif self.status == CalibrationStatus.ACTION_REQUIRED:
            self.status = CalibrationStatus.CALIBRATING


class CompassSensor(threading.Thread):
    def __init__(self, parser: CompassParser) -> None:
        super().__init__()

        self.ahrs_class = ahrs.filters.Madgwick

        self.daemon = True
        self.ser: Optional[io.RawIOBase] = None  # serial.Serial()

        self.angle: float = 0.0
        self.yaw: float = 0.0
        self.pitch: float = 0.0
        self.roll: float = 0.0
        self.heading = np.array([0.0, 0.0, 0.0])

        self.addr = None

        self.parser: CompassParser = parser

        self.ahrs_filter = self.ahrs_class()
        self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])

        self.magnetometer_calib_helper = MagnetometerCalibration()
        self.magnetometer_calibration = Calibration(
            get_sample=self.magnetometer_calib_helper.get_calibrated,
            do_calibration=self.magnetometer_calib_helper.calibrate,
        )
        self.magnetometer_calibration.calibration_instructions = (
            "Move the sensor in the shape of the number 8"
        )
        self.gyroscope_calibration: GyroCalibration = GyroCalibration()
        self.accelerometer_calibration: AccelCalibration = AccelCalibration()

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

        self.calibration_file = "calibration.npz"
        """
        File that stores sensor calibration values
        """

    def reset_ahrs_filter(self) -> None:
        self.ahrs_filter = self.ahrs_class()
        self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])

    def set_serial_device(self, sensor_dev: io.RawIOBase) -> None:
        self.ser = sensor_dev

    def run(self) -> None:
        assert self.ser is not None
        pattern = re.compile(
            r"\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*(-?\d+)\s*"
        )
        previous_time = time.time()
        while True:
            line = b""
            try:
                line = self.ser.readline()
            except Exception as e:
                messagebox.showerror(
                    "Compass sensor error",
                    f"Could not read from compass sensor, it might be disconnected. \n"
                    f"Please reconnect the sensor and then restart the python program. \n"
                    f"{str(e)}",
                )
                print(e)
                return
            if self.parser.parse(line):
                if self.parser.accelerometer_values is None:
                    print("No accelerometer value")
                    self.parser.accelerometer_values = np.array([0, 0, 0])
                if self.parser.magnetometer_values is None:
                    print("No magnetometer value")
                    self.parser.magnetometer_values = np.array([0, 0, 0])
                if self.parser.gyroscope_values is None:
                    print("No gyroscope value")
                    self.parser.gyroscope_values = np.array([0, 0, 0])

                current_time = time.time()
                self.ahrs_filter.Dt = current_time - previous_time
                self.gyroscope_values = self.gyroscope_calibration.s(
                    self.parser.gyroscope_values
                )
                self.accelerometer_values = self.accelerometer_calibration.s(
                    self.parser.accelerometer_values
                )
                self.magnetometer_values = self.magnetometer_calibration.s(
                    self.parser.magnetometer_values * 1e-6
                )  # mT
                self.ahrs_filter.gain = self.gyroscope_calibration.gyro_beta
                self.quaternion = self.ahrs_filter.updateMARG(
                    q=self.quaternion,
                    gyr=self.gyroscope_values,
                    acc=self.accelerometer_values,
                    mag=self.magnetometer_values,
                )
                previous_time = current_time
                self.heading = self.quaternion[1:4]
                self.calculate_angle()
                self.angle = self.yaw

    def calculate_angle(self) -> None:
        """
        Calculates yaw, pitch, roll from quaternion
        """
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
        if self.ser is not None:
            self.ser.close()

    def save_calibration(self) -> None:
        np.savez(
            Path(self.calibration_file),
            gyro_offsets=self.gyroscope_calibration.gyro_offsets,
            gyro_max_variance=self.gyroscope_calibration.gyro_max_variance,
            gyro_beta=np.array([self.gyroscope_calibration.gyro_beta]),
            magnetometer_soft_iron_matrix=self.magnetometer_calib_helper.A_1,
            magnetometer_hard_iron_bias=self.magnetometer_calib_helper.b,
            accelerometer_mpu_offsets=np.array(
                self.accelerometer_calibration.mpu_offsets
            ),
        )
        print(f"Compass calibration saved to {self.calibration_file}")

    def load_calibration(self) -> None:
        with np.load(Path(self.calibration_file)) as data:  # type: ignore
            self.gyroscope_calibration.gyro_offsets = data["gyro_offsets"]
            self.gyroscope_calibration.gyro_max_variance = data["gyro_max_variance"]
            self.gyroscope_calibration.gyro_beta = float(data["gyro_beta"])
            self.magnetometer_calib_helper.A_1 = data["magnetometer_soft_iron_matrix"]
            self.magnetometer_calib_helper.b = data["magnetometer_hard_iron_bias"]
            self.accelerometer_calibration.mpu_offsets = data[
                "accelerometer_mpu_offsets"
            ]
            self.gyroscope_calibration.status = CalibrationStatus.CALIBRATED
            self.magnetometer_calibration.status = CalibrationStatus.CALIBRATED
            self.accelerometer_calibration.status = CalibrationStatus.CALIBRATED
            print(f"Compass calibration loaded from {self.calibration_file}")


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
    aaronia.write(b"$PAAG,MODE,RATE,25\r\n")
    return aaronia


def open_aaronia_socket_dev(host_port: str) -> socket.SocketIO:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host_port_split = host_port.split(":")
    print(f"Connecting {host_port_split[0]} port {int(host_port_split[1])}")
    sock.connect((host_port_split[0], int(host_port_split[1])))
    print("Connected")
    sock_reader: socket.SocketIO = socket.SocketIO(sock, mode="r")
    print("Socket reader created")
    # Initializing not needed: it is done on the server side.
    # aaronia.write(b"$PAAG,MODE,START\r\n")
    # aaronia.write(b"$PAAG,MODE,RATE,25\r\n")
    return sock_reader
