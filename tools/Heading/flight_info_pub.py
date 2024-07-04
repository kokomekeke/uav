"""
DT46 FlightInfo server for testing pysagax-heading
"""

import pysagax.message.flight_info_pb2 as flight_info
from pysagax.communication.pub_sub import PUB
from time import time, sleep
from pysagax.util.mat import normalize_angle

pub = PUB(port_server=42069)
pub.connect()

position = flight_info.Position(latitude=0, longitude=0, ellipsoid_height=100, timestamp_unix=int(time()*1e6))
attitude = flight_info.Attitude(yaw=0, pitch=0, roll=0, timestamp_from_boot=1000)



while True:
    position.latitude= position.latitude + 1
    position.longitude = position.longitude + 2
    position.ellipsoid_height = int(position.ellipsoid_height * 1.01)
    position.timestamp_unix = position.timestamp_unix+100000

    attitude.yaw=normalize_angle(attitude.yaw+1.5, high=180, low=-180)
    attitude.pitch=normalize_angle(attitude.pitch+0.5, high=90, low=-90)
    attitude.roll=normalize_angle(attitude.roll-0.5, high=180, low=-180)
    attitude.timestamp_from_boot = attitude.timestamp_from_boot + 100



    packet = flight_info.UAVFlightInfo(position=position, attitude=attitude)

    pub.publ(packet.SerializeToString())

    sleep(0.1)