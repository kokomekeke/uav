"""Mocks multiple pysagaxUAV instances that all detect the same simulated target.
Useful for testing pysagaxGND and client, especially geolocation"""

from pysagax.analyzing_tools.mock.pysagax_uav_mocker import Commander
import click
import multiprocessing
import threading
from time import sleep
from pysagax.analyzing_tools.old.spotclient_recordings.nautipy import Pos, bearing
from pysagax.analyzing_tools.mock.mock_packets import *
from pysagax.util.mat import normalize_angle
from numpy import deg2rad, rad2deg

import tkinter as tk


class TargetMocker(multiprocessing.Process):
    def __init__(self, commander1_q, commander2_q, lat, lon, heading, speed, rx1_lat, rx1_lon, rx1_sigma, rx2_lat, rx2_lon, rx2_sigma):
        super().__init__(daemon=True, name="StreamProcess")

        self.commander1_q = commander1_q
        self.commander2_q = commander2_q

        self.start_time = time()

        self.lat = lat
        self.lon = lon
        self.start_pos_nautipy = Pos(float(self.lat), float(self.lon))
        self.current_pos_nautipy = self.start_pos_nautipy
        self.heading_degrees = normalize_angle(heading, 360, 0)
        self.speed_mps = speed / 3600 * 1000 # speed in m/s
        print("speed:", self.speed_mps)

        self.rx1_lat = Parameter(mu=rx1_lat, sigma=0, delta=0.0002, low_limit=-90, high_limit=90)
        self.rx1_lon = Parameter(mu=rx1_lon, sigma=0, delta=-0.0002, low_limit=-180, high_limit=180)
        self.rx2_lat = Parameter(mu=rx2_lat, sigma=0, delta=-0.0002, low_limit=-90, high_limit=90)
        self.rx2_lon = Parameter(mu=rx2_lon, sigma=0, delta=-0.0010, low_limit=-180, high_limit=180)

        self.rx1_pos = Pos(rx1_lat, rx1_lon)
        self.rx2_pos = Pos(rx2_lat, rx2_lon)

        self.rx1_sigma = rx1_sigma
        self.rx2_sigma = rx2_sigma


    def run(self) -> None:
        while True:
            sleep(0.5)
            self.generate_new_config()

    def generate_new_config(self):
        """

        """
        self.generate_current_location()
        azim1, azim2 = self.calculate_df_angles()

        self.rx1_pos = Pos(self.rx1_lat.get(), self.rx1_lon.get())

        self.rx2_pos = Pos(self.rx2_lat.get(), self.rx2_lon.get())

        lat1, lon1 = self.rx1_pos.coordinates()
        lat2, lon2 = self.rx2_pos.coordinates()


        sm1 = self.make_simulated_measurement(lat1, lon1, azim1, azim1, self.rx1_sigma)
        sm2 = self.make_simulated_measurement(lat2, lon2, azim2, azim2, self.rx2_sigma)

        self.commander1_q.put(sm1)
        self.commander2_q.put(sm2)

    def make_simulated_measurement(self, lat, lon, azimuth, mean_azimuth, deviation):
        """Make an object where every attribute is none
        except for the ones we want to modify due to moving target"""
        sm = SimulatedMeasurement(
            stream_id=None,
            config_id =None,
            overflow=None,
            peaks=None,
            heading_data = SimulatedHeading(
                packet_id = None,
                yaw=None,
                pitch=None,
                roll=None,
                gps_lat=(lat, 0, 0),
                gps_lon=(lon, 0, 0),
                altitude=None,
            ),
            detections=[
                SimulatedDetection(
                    event_id = None,
                    roi_id=None, frequency=None,
                    # azimuth=(azimuth,deg2rad(2),deg2rad(3)),
                    azimuth=(azimuth,deg2rad(deviation), 0),
                    # mean_azimuth=(mean_azimuth,deg2rad(1),deg2rad(3)),
                    mean_azimuth=(mean_azimuth,deg2rad(deviation), 0),
                    elevation=None,
                    mean_elevation=None,
                    deviation=None,
                ),
            ]
        )
        return sm

    def generate_current_location(self):
        elapsed_time = time() - self.start_time
        distance_km = elapsed_time * self.speed_mps / 1000
        self.current_pos_nautipy = self.start_pos_nautipy.displace(self.heading_degrees, distance_km)
        print("Current pos", self.current_pos_nautipy.coordinates())

    def calculate_df_angles(self):
        azim1 = deg2rad(bearing(self.rx1_pos, self.current_pos_nautipy))
        azim2 = deg2rad(bearing(self.rx2_pos, self.current_pos_nautipy))
        return azim1, azim2

@click.command()
@click.option("--level", "-l", default="INFO", show_default=True, help="Logging level")
@click.option(
    "--show-gui",
    type=bool,
    required=False,
    is_flag=True,
    show_default=False,
    default=True,
    help="Show tkinter window for easier usage",
)
@click.option(
    "--port",
    type=int,
    required=True,

    default=5556,
    help="Command port to connect to with the client or pysagaxGND",
)
@click.option(
    "--lat",
    type=float, default=0,
    help="Target starting lattitude",
)
@click.option(
    "--lon",
    type=float, default=0,
    help="Target starting longitude",
)
@click.option(
    "--heading",
    type=float, default=0,
    help="Target heading (degrees)",
)
@click.option(
    "--speed",
    type=float, default=1,
    help="Target speed (km/h)",
)
@click.option(
    "--rx1-lat",
    type=float, default=0,
    help="RX1 lattitude",
)

@click.option(
    "--rx1-lon",
    type=float, default=0,
    help="RX1 longitude",
)
@click.option(
    "--rx1-sigma",
    type=float, default=0,
    help="RX1 measured angle deviation",
)
@click.option(
    "--rx2-lat",
    type=float, default=0,
    help="RX2 lattitude",
)

@click.option(
    "--rx2-lon",
    type=float, default=0,
    help="RX2 longitude",
)
@click.option(
    "--rx2-sigma",
    type=float, default=0,
    help="RX2 measured angle deviation",
)

def main(level: str, show_gui: bool = False, port: int = 5556,
         lat=0, lon=0, heading=0, speed=1, rx1_lat=0, rx1_lon=0, rx1_sigma=0, rx2_lat=0, rx2_lon=0,  rx2_sigma=0):
    """
    TODO

    """

    # Validate logging level format
    if level is None:
        level = "INFO"
    if isinstance(level, str):
        level = level.upper()

    # Configure logging format
    from pysagax.pysagax_uav import setup_logging

    setup_logging(level=level)
    print("port", port)

    commander1 = Commander(level, port, show_gui)
    process1 = multiprocessing.Process(target=commander1.start)
    # threading.Thread(target=commander1.start).start()
    # commander1.start()
    commander2 = Commander(level, port+1, show_gui)
    process2 = multiprocessing.Process(target=commander2.start)
    # threading.Thread(target=commander2.start).start()
    # commander2.start()

    target_mocker = TargetMocker(
        commander1._gui_out_q, commander2._gui_out_q, lat=lat, lon=lon, heading=heading, speed=speed
        , rx1_lat=rx1_lat, rx1_lon=rx1_lon, rx1_sigma=rx1_sigma, rx2_lat=rx2_lat, rx2_lon=rx2_lon,  rx2_sigma=rx2_sigma,
        )

    for p in [process1, process2, target_mocker]:
        p.start()

    for p in [process1, process2, target_mocker]:
        p.join()

def run_commander(level, port):
    commander = Commander(level, port)
    commander.start()


if __name__ == "__main__":
    main()

