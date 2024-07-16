import math
import re
import time
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
from pysagax.util.read_from_conf import read_from_conf
from pysagax.util.mat import normalize_angle, rotation_matrix_from_vectors

from pysagax.communication.pub_sub import SUB
import pysagax.message.flight_info_pb2 as flight_info
from datetime import datetime
from pymavlink import mavutil


class HeadingSource:
    def __init__(self, conf: Optional[dict[str, Any]] = None) -> None:
        self.gps_updated_callback: Optional[
            Callable[[float, float, Optional[float]], None]
        ] = None
        self.quaternion_updated_callback: Optional[
            Callable[[float, float, float, float, Optional[float]], None]
        ] = None
        self.altitude_updated_callback: Optional[
            Callable[[float, Optional[float]], None]
        ] = None
        self.offset_updated_callback: Optional[Callable[[float], None]] = None
        self.data_invalid_callback: Optional[Callable[[], None]] = None
        self.status_updates_callback: Optional[Callable[[str], None]] = None
        self.quaternion = pyquaternion.Quaternion([1, 0, 0, 0])

        self.conf = conf

    def cr(self, keys, default_value):
        # shortened config parser for readablity
        if self.conf is None:
            return default_value
        return read_from_conf(self.conf, keys, default_value)

    def _gps(self, lat: float, lon: float, timestamp: Optional[float] = None) -> None:
        if self.gps_updated_callback:
            self.gps_updated_callback(lat, lon, timestamp)

    def _quaternion(
        self, quaternion: pyquaternion.Quaternion, timestamp: Optional[float] = None
    ) -> None:
        if self.quaternion_updated_callback:
            self.quaternion_updated_callback(
                quaternion[0],
                quaternion[1],
                quaternion[2],
                quaternion[3],
                timestamp,
            )

    def _altitude(self, altitude: float, timestamp: Optional[float] = None) -> None:
        if self.altitude_updated_callback:
            self.altitude_updated_callback(altitude, timestamp)

    def _offset(self, offset: float) -> None:
        if self.offset_updated_callback:
            self.offset_updated_callback(offset)

    def _data_invalid(self) -> None:
        if self.data_invalid_callback:
            self.data_invalid_callback()

    def _status(self, status: str) -> None:
        if self.status_updates_callback:
            self.status_updates_callback(status)

    def update_parameter(self, key: str, value: Any) -> bool:
        if key == "offset":
            self._offset(float(value))
        else:
            return False
        return True

    def get_parameters(self) -> dict[str, list[Any]]:
        """
        return a dict of
        config_key: [config_type, config_default_value]
        """
        return dict()

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
        self.lat: float = self.cr(
            ["heading", "static", "lat"], self.cr(["heading", "lat"], 47.498056)
        )
        self.lon: float = self.cr(
            ["heading", "static", "lon"], self.cr(["heading", "lon"], 19.04)
        )
        self.angle: float = self.cr(
            ["heading", "static", "angle"], self.cr(["heading", "angle"], 0)
        )
        self.altitude: float = self.cr(
            ["heading", "static", "altitude"], self.cr(["heading", "altitude"], 0)
        )

    def update_parameter(self, key: str, value: Any) -> bool:
        if super().update_parameter(key, value):
            return True
        if key == "angle":
            self.angle = float(value)
            self.update_heading(float(value) / 180 * np.pi, 0, 0)
            self._quaternion(self.quaternion)
        elif key == "lat":
            self.lat = float(value)
            self._gps(self.lat, self.lon)
        elif key == "lon":
            self.lon = float(value)
            self._gps(self.lat, self.lon)
        elif key == "altitude":
            self.altitude = float(value)
            self._altitude(self.altitude)
        else:
            return False
        return True

    def get_parameters(self) -> dict[str, list[Any]]:
        return {
            "lat": ["number", self.lat],
            "lon": ["number", self.lon],
            "angle": ["0-360", self.angle],
            "altitude": ["number", self.altitude],
        }

    def loop(self) -> None:
        time.sleep(0.01)
        return super().loop()


class HeadingEncoder(HeadingSource):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.connection: Optional[serial.Serial] = None
        self.port: str = self.cr(
            ["heading", "encoder", "port"], self.cr(["heading", "port"], "")
        )

        self.lat: float = self.cr(
            ["heading", "encoder", "lat"], self.cr(["heading", "lat"], 47.498056)
        )
        self.lon: float = self.cr(
            ["heading", "encoder", "lon"], self.cr(["heading", "lon"], 19.04)
        )

    def get_parameters(self) -> dict[str, list[Any]]:
        return {
            "port": ["text", self.port],
            "lat": ["number", self.lat],
            "lon": ["number", self.lon],
        }

    def update_parameter(self, key: str, value: Any) -> bool:
        if super().update_parameter(key, value):
            return True
        if key == "port":
            self.port = str(value)
        elif key == "lat":
            self.lat = float(value)
            self._gps(self.lat, self.lon)
        elif key == "lon":
            self.lon = float(value)
            self._gps(self.lat, self.lon)
        elif key == "altitude":
            self.altitude = float(value)
            self._altitude(self.altitude)
        else:
            return False
        return True

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
        except Exception:
            self._data_invalid()
            self._status("#encoder" + "Disconnected.")

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()


class HeadingAHRS(HeadingSource):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.compass: Optional[CompassBase] = None
        self.address: str = self.cr(
            ["heading", "ahrs_socket", "address"], self.cr(["heading", "address"], "")
        )
        self.use_magneto: bool = self.cr(
            ["heading", "ahrs_socket", "use_magneto"],
            self.cr(["heading", "use_magneto"], False),
        )

    def update_parameter(self, key: str, value: Any) -> bool:
        if super().update_parameter(key, value):
            return True
        if key == "address":
            self.address = str(value)
        elif key == "use_magneto":
            self.use_magneto = bool(value)
        else:
            return False
        return True

    def get_parameters(self) -> dict[str, list[Any]]:
        return {
            "address": ["text", self.address],
            "use_magneto": ["bool", self.use_magneto],
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
        if self.compass is not None and self.compass.parser is not None:
            if (
                self.compass.parser.lat is not None
                and self.compass.parser.lon is not None
            ):
                self._gps(self.compass.parser.lat, self.compass.parser.lon)
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
        self.port: str = self.cr(
            ["heading", "ahrs_usb", "port"], self.cr(["heading", "port"], "")
        )
        self.use_magneto: bool = self.cr(
            ["heading", "ahrs_usb", "use_magneto"], self.use_magneto
        )  # updating from parent clalss

    def update_parameter(self, key: str, value: Any) -> bool:
        if super().update_parameter(key, value):
            return True
        if key == "port":
            self.port = str(value)
        elif key == "use_magneto":
            self.use_magneto = bool(value)
        else:
            return False
        return True

    def get_parameters(self) -> dict[str, list[Any]]:
        return {
            "port": ["text", self.port],
            "use_magneto": ["bool", self.use_magneto],
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
        self.use_magneto: bool = self.cr(
            ["heading", "ahrs_ftdi", "use_magneto"], self.use_magneto
        )  # updating from parent clalss

    def update_parameter(self, key: str, value: Any) -> bool:
        if super().update_parameter(key, value):
            return True
        if key == "use_magneto":
            self.use_magneto = bool(value)
        else:
            return False
        return True

    def get_parameters(self) -> dict[str, list[Any]]:
        return {
            "use_magneto": ["bool", self.use_magneto],
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


class HeadingFlightInfo(HeadingSource):
    """
    Heading data supplied by the DT46 drone in used in the ALTISS project.
    The data arrives in protobuf packets using ZeroMQ's PUB/SUB pattern.
    """

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.address: str = self.cr(
            ["heading", "FlightInfo", "address"],
            self.cr(["heading", "address"], "127.0.0.1"),
        )
        self.port: int = self.cr(
            ["heading", "FlightInfo", "port"], self.cr(["heading", "port"], 42069)
        )

        self._sub: Optional[SUB] = None

    def get_parameters(self) -> dict[str, list[Any]]:
        return {
            "address": ["text", self.address],
            "port": ["number", self.port],
        }

    def update_parameter(self, key: str, value: Any) -> bool:
        if super().update_parameter(key, value):
            return True
        if key == "address":
            self.address = str(value)
        elif key == "port":
            self.port = int(value)
        else:
            return False
        return True

    def initialize(self) -> bool:
        try:
            self._sub = SUB(address_server=self.address, port_server=self.port)
            self._sub.connect()
            self._status(f"FlightInfo connected on {self.address}:{self.port}")
            return True
        except:
            self._status(f"FlightInfo faield to connect on {self.address}:{self.port}")
            return False

    def loop(self) -> None:
        if not self._sub:
            return

        try:
            packet_b = self._sub.receive(timeout=1000)
            if packet_b is None:
                # timeout
                return
            packet = flight_info.UAVFlightInfo()
            packet.ParseFromString(packet_b)

            timestamp_s = float(packet.position.timestamp_unix) / 1e6  # convert us to s
            self._gps(packet.position.latitude, packet.position.longitude, timestamp_s)
            self._altitude(packet.position.ellipsoid_height, timestamp_s)

            self.update_heading(
                yaw=packet.attitude.yaw / 180 * np.pi,
                pitch=packet.attitude.pitch / 180 * np.pi,
                roll=packet.attitude.roll / 180 * np.pi,
            )
            self._quaternion(self.quaternion, timestamp_s)

        except:
            self._data_invalid()
            self._status("Received invalid FlightInfo message.")

    def close(self) -> None:
        if self._sub:
            self._sub.disconnect()


class HeadingMavlink(HeadingSource):
    """
    Mavlink source
    """

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.address: str = self.cr(
            ["heading", "Mavlink", "address"],
            self.cr(["heading", "address"], "127.0.0.1"),
        )
        self.port: int = self.cr(
            ["heading", "Mavlink", "port"], self.cr(["heading", "port"], 14540)
        )

        self._mavs: Any = None

    def get_parameters(self) -> dict[str, list[Any]]:
        return {
            "address": ["text", self.address],
            "port": ["number", self.port],
        }

    def update_parameter(self, key: str, value: Any) -> bool:
        if super().update_parameter(key, value):
            return True
        if key == "address":
            self.address = str(value)
        elif key == "port":
            self.port = int(value)
        else:
            return False
        return True

    def initialize(self) -> bool:
        try:
            self._mavs = mavutil.mavlink_connection(
                f"udp:{self.address}:{self.port}",
                input=True,
            )
            self._status(f"Mavlink listens on UDP {self.address}:{self.port}")
            return True
        except:
            self._status(f"Mavlink fails on UDP {self.address}:{self.port}")
            return False

    def loop(self) -> None:
        if not self._mavs:
            return

        try:
            msg = self._mavs.recv_msg()
            timestamp_s = datetime.timestamp(datetime.now()) * 1000
            if msg is not None:
                msg_type = msg.get_type()
                if "ATTITUDE" == msg_type:
                    roll = getattr(msg, "roll")
                    pitch = getattr(msg, "pitch")
                    yaw = getattr(msg, "yaw")

                    self.update_heading(
                        yaw=yaw / 180 * np.pi,
                        pitch=pitch / 180 * np.pi,
                        roll=roll / 180 * np.pi,
                    )
                    self._quaternion(self.quaternion, timestamp_s)
                if "GLOBAL_POSITION_INT" in msg_type:
                    lat = getattr(msg, "lat")
                    lon = getattr(msg, "lon")
                    alt = getattr(msg, "alt")
                    self._gps(lat, lon, timestamp_s)
                    self._altitude(alt, timestamp_s)

        except TypeError as e:
            self._data_invalid()
            self._status("Mavlink message invalid.")

    def close(self) -> None:
        if self._mavs:
            self._mavs.close()
