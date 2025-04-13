import pysagax.message.flight_info_pb2 as flight_info
from random import random
from pysagax.communication.pub_sub import PUB
from time import time, sleep
from pysagax.util.mat import normalize_angle
import os
import click
from math import cos, sin, sqrt

import zmq

@click.command()
@click.option("--port", "-p", default=42069, help="Port for PUB server")
@click.option(
    "--constant-ypr",
    is_flag=True,
    default=False,
    help="Supply constant height and attitude data.",
)
@click.option(
    "--ocsa-circle",
    is_flag=True,
    default=False,
    help="Simulate a circular path over Ocsa base",
)
def main(port, constant_ypr, ocsa_circle):
    """
    Mock DT46 FlightInfo server for testing pysagax-heading.

    --ocsa-circle:
        False: publish heading data that mocks an UAV flying along the M5 highway in Hungary
        True: publish heading data mocking flying circles over Ócsa military base
    """
    # pub = PUB(port_server=port)
    # pub.connect()
    context = zmq.Context()
    pub = context.socket(zmq.PUB)
    address = f"tcp://*:{port}"
    pub.bind(address)

    # 47.3274,19.2556
    # 46.8865,19.6502

    if ocsa_circle:
        fly_ocsa_circle(pub, port)
    else:
        fly_straight_line(pub, port, constant_ypr)

def fly_straight_line(pub, port, constant_ypr):
    position = flight_info.Position(
        latitude=47.3274,
        longitude=19.2556,
        ellipsoid_height=100,
        timestamp_unix=int(time() * 1e6),
    )
    attitude = flight_info.Attitude(yaw=150, pitch=2, roll=-3, timestamp_from_boot=1000)

    i = 0
    while True:
        position.latitude = position.latitude + (-0.00004408999999999992) 
        position.longitude = position.longitude + 0.00003946000000000005  
        position.timestamp_unix = position.timestamp_unix + 100000

        if not constant_ypr:
            position.ellipsoid_height = int(position.ellipsoid_height + 0.001)
            attitude.yaw = normalize_angle(attitude.yaw + 1.5, high=180, low=-180)
            attitude.pitch = normalize_angle(attitude.pitch + 0.5, high=90, low=-90)
            attitude.roll = normalize_angle(attitude.roll - 0.5, high=180, low=-180)
        attitude.timestamp_from_boot = attitude.timestamp_from_boot + 100

        publish_flight_info(port, pub, position, attitude, i)
        i += 1

def fly_ocsa_circle(pub, port):
    center_lat = 47.324153
    center_lon = 19.314815
    radius_meter = 400
    radius_lat = radius_meter / 111190
    radius_lon = radius_meter / 75370

    position = flight_info.Position(
        latitude=47.3274,
        longitude=19.2556,
        ellipsoid_height=70,
        timestamp_unix=int(time() * 1e6),
    )
    attitude = flight_info.Attitude(yaw=150, pitch=2, roll=-3, timestamp_from_boot=1000)

    theta = 0
    i = 0
    while True:
        position.latitude = center_lat + radius_lat * cos(theta)
        position.longitude = center_lon + radius_lon * sin(theta)

        position.timestamp_unix = position.timestamp_unix + 100000

        # attitude.yaw = theta * 180 / 3.1415 + 90
        attitude.yaw = theta * 180 / 3.1415 - 90 # counter clockwise
    
        # # # offset error from spider recordings compensated
        # # attitude.yaw = attitude.yaw - 2.3
        # attitude.yaw = attitude.yaw - 4.3

        # a little random noise to make it more belivable
        position.ellipsoid_height = position.ellipsoid_height + random() - 0.5
        attitude.yaw = attitude.yaw + random() / 10
        attitude.pitch = attitude.pitch + (random()-0.5) / 10
        attitude.roll = attitude.roll + (random()-0.5) / 10


        publish_flight_info(port, pub, position, attitude, i)

        # theta = theta + (0.5 * 3.1415 / 180)
        theta = theta - (0.5 * 3.1415 / 180)
        theta = normalize_angle(theta)
        i += 1


def publish_flight_info(port, pub, position, attitude, i):
    packet = flight_info.UAVFlightInfo(position=position, attitude=attitude)

    # pub.publ(packet.SerializeToString())
    pub.send_multipart([b'fi', packet.SerializeToString()])
        # pub.publ(b'fi')
    if not i % 10:
        os.system("clear")
        print(f"FlightInfo server up on port {port} \n\n{packet}")
    sleep(0.1)


if __name__ == "__main__":
    main()
