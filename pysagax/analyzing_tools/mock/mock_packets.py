from time import time, sleep
from numpy import deg2rad, rad2deg
from typing import Iterable

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading

from pysagax.util.mat import si_to_float, quat, ypr, normalize_angle

import google.protobuf.message
import numpy as np


class Parameter:
    def __init__(self, mu, sigma, delta, low_limit=None, high_limit=None):
        """
        A single simulated parameter generated using normal distribution
        mu: current mean of distribution
        sigma: deviation
        delta: change of mu per second

        if low_limit and high_limit are defined -> 
        the result is treated as circular data, and is normalized between the limits. (eg. angles)
        """
        self.mu = mu
        self.sigma = sigma
        self.delta = delta

        self._low_limit = low_limit
        self._high_limit = high_limit

        self._last_called = time()

    @classmethod
    def from_tuple(cls, values, low_limit=None, high_limit=None):
        if values == None:
            # for initializing packets that are used to update certain parameters
            return None
        return cls(values[0], values[1], values[2], low_limit, high_limit)

    def get(self):
        current_time = time()
        self.mu = self.mu + self.delta * (current_time - self._last_called)
        self._last_called = current_time
        result = np.random.normal(self.mu, self.sigma)
        if self._low_limit is None:
            return result
        return normalize_angle(result, high=self._high_limit, low=self._low_limit)


class SimulatedPacket:
    def __init__(self):
        pass

    def update(self, new):
        """
        Updates the current object's attributes with the values from another 
        SimulatedMeasurement object, but only if the values are not None. 
        """
        for attr, value in vars(new).items():
            if value is None:
                continue
            if isinstance(value, Iterable) and all(isinstance(x, SimulatedPacket) for x in value):
                # list of some sort of simulated packets (eg. detections)
                for i, x in enumerate(value):
                    if i < len(getattr(self, attr)):
                        getattr(self, attr)[i].update(x)
                    else:
                        new_object = type(x)()
                        new_object.update(x)
                        getattr(self, attr).append(new_object)
            elif isinstance(value, SimulatedPacket):
                getattr(self, attr).update(value)
            else:
                setattr(self, attr, value)


class SimulatedDetection(SimulatedPacket):
    def __init__(
            self,
            event_id=0,
            roi_id=0,
            frequency=(446e6, 0, 0),
            azimuth=(0, deg2rad(1), deg2rad(1)),
            mean_azimuth=(0, deg2rad(1), deg2rad(1)),
            elevation=(0, deg2rad(1), deg2rad(1)),
            mean_elevation=(0, deg2rad(1), deg2rad(1)),
            deviation=(0, 0, 0),

    ):
        super().__init__()
        self.event_id = event_id
        self.roi_id = roi_id
        self.frequency = Parameter.from_tuple(frequency)
        self.azimuth = Parameter.from_tuple(azimuth, -np.pi, np.pi)
        self.mean_azimuth = Parameter.from_tuple(mean_azimuth, -np.pi, np.pi)
        self.elevation = Parameter.from_tuple(elevation, -np.pi, np.pi)
        self.mean_elevation = Parameter.from_tuple(mean_elevation, -np.pi, np.pi)
        self.deviation = Parameter.from_tuple(deviation, -np.pi, np.pi)

    def get_packet(self):
        packet = proto_data.Detection(
            event_id=self.event_id,
            roi_id=self.roi_id,
            frequency=self.frequency.get(),
            azimuth=self.azimuth.get(),
            mean_azimuth=self.mean_azimuth.get(),
            elevation=self.elevation.get(),
            mean_elevation=self.mean_elevation.get(),
            deviation=self.deviation.get(),
        )
        return packet


class SimulatedHeading(SimulatedPacket):
    def __init__(
            self,
            packet_id=0,
            yaw=(0, 0, 0),
            pitch=(0, 0, 0),
            roll=(0, 0, 0),
            gps_lat=(47.3253, 0, 0),
            gps_lon=(19.3123, 0, 0),
            altitude=(100, 0, 0),
            offset=0,

    ):
        super().__init__()
        self.packet_id = packet_id
        self.yaw = Parameter.from_tuple(yaw, -np.pi, np.pi)
        self.pitch = Parameter.from_tuple(pitch, -np.pi / 2, np.pi / 2)
        self.roll = Parameter.from_tuple(roll, -np.pi, np.pi)
        self.gps_lat = Parameter.from_tuple(gps_lat, -90, 90)
        self.gps_lon = Parameter.from_tuple(gps_lon, -180, 180)
        self.altitude = Parameter.from_tuple(altitude)
        self.offset = offset

    def get_packet(self):
        quaternion = quat(self.yaw.get(), self.pitch.get(), self.roll.get())
        packet = proto_heading.HeadingData(
            packet_id=self.packet_id,
            quaternion=quaternion,
            gps_lat=self.gps_lat.get(),
            gps_lon=self.gps_lon.get(),
            altitude=self.altitude.get(),
            offset=self.offset
        )

        timestamp = time()
        packet.timestamp.seconds = int(timestamp)
        packet.timestamp.nanos = int(timestamp % 1 * 1e9)
        packet.gps_time.seconds = int(timestamp)
        packet.gps_time.nanos = int(timestamp % 1 * 1e9)

        return packet


class SimulatedMeasurement(SimulatedPacket):
    def __init__(self, stream_id=0,
                 config_id=0,
                 overflow=False,
                 peaks=(10000, 10000, 10000, 10000),
                 heading_data=SimulatedHeading(),
                 detections=[]):
        super().__init__()
        if detections is None:
            detections = []
        self.stream_id = stream_id,
        self.config_id = config_id
        self.overflow = overflow
        self.peaks = peaks  # TODO: simulated
        self.heading_data = heading_data
        self.detections: list[SimulatedDetection] = detections

    def get_packet(self):
        packet = proto_data.Measurement()
        timestamp = time()
        packet.time.seconds = int(timestamp)
        packet.time.nanos = int(timestamp % 1 * 1e9)

        packet.config_id = self.config_id
        packet.overflow = self.overflow
        packet.peaks.extend(self.peaks)
        packet.heading_data.CopyFrom(self.heading_data.get_packet())

        for d in self.detections:
            packet.detection.append(d.get_packet())
        return packet

    # def update(self, new):
    #     """
    #     Updates the current object's attributes with the values from another 
    #     SimulatedMeasurement object, but only if the values are not None. 
    #     """
    #     for attr, value in vars(new).items():
    #         if value is not None:
    #             setattr(self, attr, value)
