"""
DT46 FlightInfo server for testing pysagax-heading
"""

import pysagax.message.flight_info_pb2 as flight_info
from pysagax.communication.pub_sub import PUB
from time import time, sleep
from pysagax.util.mat import normalize_angle
import os

pub = PUB(port_server=42069)
pub.connect()

position = flight_info.Position(latitude=43.03, longitude=17.4, ellipsoid_height=100, timestamp_unix=int(time()*1e6))
attitude = flight_info.Attitude(yaw=0, pitch=0, roll=0, timestamp_from_boot=1000)


i = 0
while True:
    position.latitude= position.latitude + 0.00005
    position.longitude = position.longitude + 0.0001
    position.ellipsoid_height = int(position.ellipsoid_height + 0.001)
    position.timestamp_unix = position.timestamp_unix+100000

    attitude.yaw=normalize_angle(attitude.yaw+1.5, high=180, low=-180)
    attitude.pitch=normalize_angle(attitude.pitch+0.5, high=90, low=-90)
    attitude.roll=normalize_angle(attitude.roll-0.5, high=180, low=-180)
    attitude.timestamp_from_boot = attitude.timestamp_from_boot + 100



    packet = flight_info.UAVFlightInfo(position=position, attitude=attitude)

    pub.publish(packet.SerializeToString())
    # pub.publ(b'fi')
    if not i % 10:
        os.system('clear')
        print(packet)
    sleep(0.1)
    i +=1