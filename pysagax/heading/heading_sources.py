import math
import re
from typing import Any, Callable, Optional

import numpy as np
import pyquaternion
import serial

from pysagax.df.compass_sensors import (
    AaroniaParser,
    CompassBase,
    open_aaronia_serial_dev,
    open_aaronia_socket_dev,
    open_arduino_serial_dev,
)
from pysagax.util.confreader import confreader
from pysagax.util.mat import normalize_angle, rotation_matrix_from_vectors


class HeadingSource:
    def __init__(self, conf) -> None:
        self.gps_updated_callback: Optional[Callable[[float, float], None]] = None
        self.quaternion_updated_callback: Optional[
            Callable[[float, float, float, float], None]
        ] = None
        self.data_invalid_callback: Optional[Callable[[], None]] = None
        self.status_updates_callback: Optional[Callable[[str], None]] = None
        self.quaternion = pyquaternion.Quaternion([1, 0, 0, 0])

        self.conf = conf

    def cr(self, keys, default_value):
        # shortened config parser for readablity
        return confreader(self.conf, keys, default_value)

    def _gps(self, lat: float, lon: float) -> None:
        if self.gps_updated_callback:
            self.gps_updated_callback(lat, lon)

    def _quaternion(self, quaternion: pyquaternion.Quaternion) -> None:
        if self.quaternion_updated_callback:
            self.quaternion_updated_callback(
                quaternion[0], quaternion[1], quaternion[2], quaternion[3]
            )

    def _data_invalid(self) -> None:
        if self.data_invalid_callback:
            self.data_invalid_callback()

    def _status(self, status: str) -> None:
        if self.status_updates_callback:
            self.status_updates_callback(status)

    def update_parameter(self, key: str, value: Any) -> None:
        pass

    def get_parameters(self) -> dict[str, str]:
        """
        Values here are parsed for child classes to use as default parameters.
        Makes it possible to use generic config parameters for all heading sources
        or specific ones for each source type as desired.
        return dict: key -> [type, default value]
        """
        return {
            "lat": ["number", self.cr(["heading", "lat"], 47.498056)],
            "lon": ["number", self.cr(["heading", "lon"], 19.04)],
            "angle": ["0-360", self.cr(["heading", "angle"], 0)],
            "address": ["text", self.cr(["heading", "address"], "")],
            "port": ["text", self.cr(["heading", "port"], "")],
            "use_magneto": ["bool", self.cr(["heading", "use_magneto"], False)],
        }

    def initialize(self) -> bool:
        return False

    def close(self) -> None:
        pass

    def loop(self) -> None:
        pass

    def update_heading(self, yaw: float, pitch: float, roll: float) -> None:
        self.quaternion = (
            pyquaternion.Quaternion(axis=[0, 0, 1], angle=yaw)
            * pyquaternion.Quaternion(axis=[0, 1, 0], angle=pitch)
            * pyquaternion.Quaternion(axis=[1, 0, 0], angle=roll)
        )


class HeadingStatic(HeadingSource):
    def initialize(self) -> bool:
        return True

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.lat: float = 0.0
        self.lon: float = 0.0

    def update_parameter(self, key: str, value: Any) -> None:
        if key == "angle":
            self.update_heading(float(value) / 180 * np.pi, 0, 0)
            self._quaternion(self.quaternion)
        elif key == "lat":
            self.lat = float(value)
            self._gps(self.lat, self.lon)
        elif key == "lon":
            self.lon = float(value)
            self._gps(self.lat, self.lon)

    def get_parameters(self) -> dict[str, str]:
        defaults = super().get_parameters()

        lat = self.cr(["heading", "static", "lat"], defaults["lat"][1])
        lon = self.cr(["heading", "static", "lon"], defaults["lon"][1])
        angle = self.cr(["heading", "static", "angle"], defaults["angle"][1])
        return {
            "lat": ["number", lat],
            "lon": ["number", lon],
            "angle": ["0-360", angle],
        }


class HeadingEncoder(HeadingSource):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.connection: Optional[serial.Serial] = None
        self.port: str = ""

        self.lat = 0.0
        self.lon = 0.0

    def get_parameters(self) -> dict[str, str]:
        defaults = super().get_parameters()

        lat = self.cr(["heading", "encoder", "lat"], defaults["lat"][1])
        lon = self.cr(["heading", "encoder", "lon"], defaults["lon"][1])
        port = self.cr(["heading", "encoder", "port"], defaults["port"][1])
        return {
            "port": ["text", port],
            "lat": ["number", lat],
            "lon": ["number", lon],
        }

    def update_parameter(self, key: str, value: Any) -> None:
        if key == "port":
            self.port = str(value)

        elif key == "lat":
            self.lat = float(value)
            self._gps(self.lat, self.lon)
        elif key == "lon":
            self.lon = float(value)
            self._gps(self.lat, self.lon)

    def initialize(self) -> bool:
        try:
            self.connection = serial.Serial(self.port, baudrate=9600, timeout=0.5)
            self._status("#encoder" + "Connected")
            return True
        except:
            self._status(
                "#encoder" + f"Could not connect to encoder on port {self.port}"
            )
            return False

    def loop(self) -> None:
        if self.connection is None:
            return
        try:
            msg = self.connection.readline()
            ctr = re.findall(r"\d+\.\d+", str(msg))
            if len(ctr):
                self.update_heading(normalize_angle(float(ctr[0])), 0, 0)
                self._quaternion(self.quaternion)
        except:
            self._data_invalid()
            self._status("#encoder" + "Disconnected.")

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()


class HeadingAHRS(HeadingSource):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.compass: Optional[CompassBase] = None
        self.address: str = ""
        self.use_magneto: bool = False

    def update_parameter(self, key: str, value: Any) -> None:
        if key == "address":
            self.address = str(value)
        elif key == "use_magneto":
            self.use_magneto = bool(value)

    def get_parameters(self) -> dict[str, str]:
        defaults = super().get_parameters()
        address = self.cr(["heading", "ahrs_socket", "address"], defaults["address"][1])
        use_magneto = self.cr(
            ["heading", "ahrs_socket", "use_magneto"], defaults["use_magneto"][1]
        )
        return {
            "address": ["text", address],
            "use_magneto": ["bool", use_magneto],
        }

    def calibrate(self) -> None:
        if self.compass is None:
            return
        try:
            self.compass.load_calibration()
        except FileNotFoundError:
            self._status(
                "#compass"
                + "Startup error, Calibration file calibration.npz not found. Make sure sgx-pc is your workdir"
            )

    def initialize(self) -> bool:
        self.compass = CompassBase(AaroniaParser())

        self.calibrate()
        try:
            self.compass.set_serial_device(open_aaronia_socket_dev(self.address))
            self._status("#compass" + "Connected")
            return True
        except serial.SerialException:
            self._status("#compass" + "Compass sensor not connected")
            return False
        except ConnectionError as e:
            self._status("#compass" + str(e))
            self.compass = None
            return False
        except IndexError as e:
            self._status("#compassInvalid address" + str(e))
            self.compass = None
            return False

    def loop(self) -> None:
        if not self.compass:
            return
        self.compass.loop()
        if self.use_magneto:
            magneto = self.compass.magnetometer_values
            if magneto is None:
                self._data_invalid()
                return
            north = np.asarray([-1, 0, 0])
            norm = np.linalg.norm(magneto)
            if norm == 0:
                self._data_invalid()
                return
            magneto_n = magneto / norm

            q = pyquaternion.Quaternion(
                matrix=rotation_matrix_from_vectors(north, magneto_n)
            )
            self._quaternion(q)
        else:
            self._quaternion(self.compass.quaternion)

    def close(self) -> None:
        if self.compass:
            self.compass.close()


class HeadingAHRSUSB(HeadingAHRS):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.port: str = ""

    def update_parameter(self, key: str, value: Any) -> None:
        if key == "port":
            self.port = str(value)
        elif key == "use_magneto":
            self.use_magneto = bool(value)

    def get_parameters(self) -> dict[str, str]:
        defaults = HeadingSource.get_parameters(self)
        port = self.cr(["heading", "ahrs_usb", "port"], defaults["port"][1])
        use_magneto = self.cr(
            ["heading", "ahrs_usb", "use_magneto"], defaults["use_magneto"][1]
        )
        return {
            "port": ["text", port],
            "use_magneto": ["bool", use_magneto],
        }

    def initialize(self) -> bool:
        self.compass = CompassBase(AaroniaParser())
        self.calibrate()
        try:
            self.compass.set_serial_device(open_arduino_serial_dev(self.port))

            self._status("#compass" + "Connected")
            return True
        except serial.SerialException:
            self._status("#compass" + "Compass sensor not connected")
            return False
        except ConnectionError as e:
            self._status("#compass" + str(e))
            self.compass = None
            return False


class HeadingAHRSFTDI(HeadingAHRS):
    def __init__(self, *args) -> None:
        super().__init__(*args)

    def update_parameter(self, key: str, value: Any) -> None:
        if key == "use_magneto":
            self.use_magneto = bool(value)

    def get_parameters(self) -> dict[str, str]:
        defaults = HeadingSource.get_parameters(self)
        use_magneto = self.cr(
            ["heading", "ahrs_ftdi", "use_magneto"], defaults["use_magneto"][1]
        )
        return {
            "use_magneto": ["bool", use_magneto],
        }

    def initialize(self) -> bool:
        self.compass = CompassBase(AaroniaParser())
        self.calibrate()

        try:
            self.compass.set_serial_device(open_aaronia_serial_dev())

            self._status("#compass" + "Connected")
            return True
        except serial.SerialException:
            self._status("#compass" + "Compass sensor not connected")
            return False
        except ConnectionError as e:
            self._status("#compass" + str(e))
            self.compass = None
            return False
