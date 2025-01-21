

from pysagax.message.proto_stream_to_file import FileStreamer
import pysagax.message.data_pb2 as proto_data
from pysagax.util.protobuf_spectrum_utils import protobuf_spectrum_to_numpy
from google.protobuf.timestamp_pb2 import Timestamp
from time import time
import click
import pandas as pd
from scipy.spatial.transform import Rotation

@click.command()
@click.option(
    "-p",
    "--path",
    type=str,
    required = True,
    help="Location for the .protorec file that is to be parsed",
)
# @click.option(
#     "-t",
#     "--threshold",
#     type=float,
#     default=None,
#     required = False,
#     help="Replace values below this with nan",
# )
# @click.option("--radians", "-r", is_flag=True, show_default=True, default=False,
#               help="Plot azimuth and elevation spectrograms using radian values")
def main(path:str):#, radians:bool, threshold = None):
    """Creates a .csv file from a .protorec that contains the heading info"""
    # file_streamer = FileStreamer("pysagax/gany/proto_file_stream/recordings/test_scan.protorec", "playback")
    # file_streamer = FileStreamer("pysagax/gany/proto_file_stream/recordings/test_float16_65k-65k_20240606_125722.protorec", "playback")
    file_streamer = FileStreamer(path, mode="playback")
    packet_list: list[proto_data.Measurement]
    start = time()
    time_list, packet_list = file_streamer.read_all()

    df = pd.DataFrame()
    df["record_time"] = time_list
    df["packet_time"] = [p.time.ToNanoseconds()/1e9 for p in packet_list]
    df["heading_time"] = [p.heading_data.timestamp.ToNanoseconds()/1e9 for p in packet_list]
    df["gps_time"] = [p.heading_data.gps_time.ToNanoseconds()/1e9 for p in packet_list]
    df["q0"] = [p.heading_data.quaternion[0] if len(p.heading_data.quaternion) else None for p in packet_list]
    df["q1"] = [p.heading_data.quaternion[1] if len(p.heading_data.quaternion) else None for p in packet_list]
    df["q2"] = [p.heading_data.quaternion[2] if len(p.heading_data.quaternion) else None for p in packet_list]
    df["q3"] = [p.heading_data.quaternion[3] if len(p.heading_data.quaternion) else None for p in packet_list]

    attitude_list = []
    for p in packet_list:
        try:
            attitude_list.append(Rotation.from_quat(p.heading_data.quaternion[1:] + p.heading_data.quaternion[:1]) if len(p.heading_data.quaternion) == 4 else None)
        except: # 0-norm quaternion
            attitude_list.append(None)

    # attitude_list = [Rotation.from_quat(p.heading_data.quaternion[1:] + p.heading_data.quaternion[:1]) if len(p.heading_data.quaternion) == 4 else None for p in packet_list]
    attitude_euler_list = [a.as_euler("ZYX", degrees=True) if a is not None else None for a in attitude_list]
    df["yaw"] = [a[0] if a is not None else None for a in attitude_euler_list]
    df["pitch"] = [a[1] if a is not None else None  for a in attitude_euler_list]
    df["roll"] = [a[2] if a is not None else None  for a in attitude_euler_list]
    # yaw, pitch, roll = attitude.as_euler("ZYX", degrees=True)



    df["lat"] = [p.heading_data.gps_lat for p in packet_list]
    df["lon"] = [p.heading_data.gps_lon for p in packet_list]
    df["altitude"] = [p.heading_data.altitude for p in packet_list]
    df["offset"] = [p.heading_data.offset for p in packet_list]

    print(f"Saving to: ", "".join(path.split(".")[:-1]) + "heading.csv")
    df.to_csv("".join(path.split(".")[:-1]) + "heading.csv")
    
if __name__ == "__main__":
    main()