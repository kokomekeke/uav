

from pysagax.message.proto_stream_to_file import FileStreamer
import pysagax.message.data_pb2 as proto_data
from pysagax.util.protobuf_spectrum_utils import protobuf_spectrum_to_numpy
from google.protobuf.timestamp_pb2 import Timestamp
from time import time
import click
import pandas as pd
from scipy.spatial.transform import Rotation
import json
import pyquaternion
import numpy as np

def ypr(w, x, y, z, degrees=False):
    """Convert quaternion to Euler angles"""
    try:
        a = Rotation.from_quat([x, y, z, w])
    except ValueError:  # 0-norm quaternions or nans
        return [float("nan")] * 3
    return a.as_euler("ZYX", degrees=degrees)

def quat(y, p, r, degrees=False):
    """Convert Euler angles to quaternion in scalar-first form: [w, x, y, z]"""
    a = Rotation.from_euler("ZYX", [y, p, r], degrees=degrees)
    q_scalar_last = a.as_quat()
    q = np.concatenate((q_scalar_last[-1:], q_scalar_last[:-1]))
    return q


@click.command()
@click.option(
    "-p",
    "--path",
    type=str,
    required = True,
    help="Location for the .txt file from Magellium",
)
def main(path:str):
    """
    Reads data from the .txt file provided by Magellium and saves the data to a .csv file
    """
    # file_streamer = FileStreamer("pysagax/gany/proto_file_stream/recordings/test_scan.protorec", "playback")
    # file_streamer = FileStreamer("pysagax/gany/proto_file_stream/recordings/test_float16_65k-65k_20240606_125722.protorec", "playback")
    
    file_io =  open(path, "r")
    
    record_times = []
    heading_times = []
    yaws = []
    pitches = []
    rolls  = []
    packets = []
    for line in file_io.readlines():
        packet = json.loads(line)
        packets.append(packet)


    df = pd.DataFrame()
    df["record_time"] = [p['timestamp'] for p in packets]
    # df["packet_time"] = [p.time.ToNanoseconds()/1e9 for p in packet_list]
    df["heading_time"] = [p['position']['timestampUnix'] for p in packets]
    # df["gps_time"] = [p.heading_data.gps_time.ToNanoseconds()/1e9 for p in packet_list]

    quat_list = []
    for p in packets:
        try:
            yaw =p['attitude']['yaw']
            pitch =p['attitude']['pitch']
            roll=p['attitude']['roll']
        except KeyError:
            yaw, pitch, roll = float('nan'),float('nan'),float('nan')

        quaternion = quat(yaw, pitch, roll, degrees=True)
        quat_list.append(quaternion)
        
        # quaternion = (
        #     pyquaternion.Quaternion(axis=[0, 0, 1], angle=yaw)
        #     * pyquaternion.Quaternion(axis=[0, 1, 0], angle=pitch)
        #     * pyquaternion.Quaternion(axis=[1, 0, 0], angle=roll)
        # )
        # quat_list.append(quaternion)
        # try:
        #     attitude_list.append(Rotation.from_quat(p.heading_data.quaternion[1:] + p.heading_data.quaternion[:1]) if len(p.heading_data.quaternion) == 4 else None)
        # except: # 0-norm quaternion
        #     attitude_list.append(None)
    

    df["q0"] = [q[0] for q in quat_list]
    df["q1"] = [q[1] for q in quat_list]
    df["q2"] = [q[2] for q in quat_list]
    df["q3"] = [q[3] for q in quat_list]

    df["yaw"] = [p['attitude']['yaw'] if 'yaw' in p['attitude'] else float('nan') for p in packets]
    df["pitch"] = [p['attitude']['pitch'] if 'pitch' in p['attitude'] else float('nan')  for p in packets]
    df["roll"] = [p['attitude']['roll'] if 'roll' in p['attitude'] else float('nan')  for p in packets]



    df["lat"] = [p['position']['latitude'] for p in packets]
    df["lon"] = [p['position']['longitude'] for p in packets]
    df["altitude"] = [p['position']['ellipsoidHeight'] for p in packets]
    # df["offset"] = [p.heading_data.offset for p in packet_list]

    print(f"Saving to: ", "".join(path.split(".")[:-1]) + "DT46_heading.csv")
    df.to_csv("".join(path.split(".")[:-1]) +  "DT46_heading.csv")
    
if __name__ == "__main__":
    main()