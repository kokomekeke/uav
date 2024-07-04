import datetime
import math
import os
import re
import sys
import time
from  matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import scipy
from geographiclib.geodesic import Geodesic
# import pysagax 

# TRANSMITTER_LAT = 47.321013 #forgato 
# TRANSMITTER_LON = 19.316929   #forgato

TRANSMITTER_LAT = 47.320048
TRANSMITTER_LON = 19.317817

USE_STATIONARY_RX_COORDINATES = True
RECIEVER_LAT = 47.321019    #fl2
RECIEVER_LON = 19.316908    #fl2
# RECIEVER_LAT = 47.320746    #fl1
# RECIEVER_LON = 19.316848    #fl1
COMPASS_HEADING = 45*np.pi/180
# COMPASS_HEADING = 0
DATE_OF_RECORDING_YMD = [2023, 11, 9]

CHANGE_ROTATION_DIR = True #false for field laptop 1 on 231109 day, true for fl2

folder = "C:\\Users\\p\\Documents\\measurments\\ocsa_231109\\5\\2\\c\\"
# folder = "C:\\Users\\p\\Documents\\measurments\\ocsa_231113\\moving_drones_1_2merged\\New folder\\"
client_data_file = "20231109_154038.csv"
output_file = client_data_file[:-4] + "_merged.csv"
recording_correct_first_timestamp_ns = 0 #if not 0 then the time_ns column will be shifted to start from this value (for correcting recordings made from sigmf playback) (use unix timestamp in ns!)


def normalize_angle(angle: float, high: float = np.pi, low: float = -np.pi) -> float:
    span = high - low
    while angle >= high:
        angle = angle - span
    while angle < low:
        angle = angle + span
    return angle

def azim_and_dist_from_points(lat_tx, lon_tx, lat_rx=RECIEVER_LAT, lon_rx=RECIEVER_LON):
    ##calculate gt azimuth and distance from transmitter and reciever coordinates
    result = Geodesic.WGS84.Inverse(lat_rx, lon_rx, lat_tx, lon_tx)
    # print(result)
    azim = result["azi1"] * np.pi / 180
    dist = result["s12"]
    return azim, dist

measures = pd.read_csv(f"{folder}{client_data_file}")

if recording_correct_first_timestamp_ns:
    measures["time_ns"] = measures["time_ns"] - measures["time_ns"][0] + recording_correct_first_timestamp_ns


result = measures
result.insert(loc=len(result.columns), column="seconds", value=float("nan"))
result.insert(loc=len(result.columns), column="time", value=float("nan"))
result.insert(loc=len(result.columns), column="lat_tx", value=float(TRANSMITTER_LAT))
result.insert(loc=len(result.columns), column="lon_tx", value=float(TRANSMITTER_LON))
if USE_STATIONARY_RX_COORDINATES:
    result["lat"] = RECIEVER_LAT
    result["lon"] = RECIEVER_LON
    result["compass_angle"] = COMPASS_HEADING
    result["compass_heading"] = COMPASS_HEADING

result["seconds"] = (result["time_ns"] - result["time_ns"][0]) / 1e9 
result["time"] = (result["time_ns"]/1e9).map(lambda ts: datetime.datetime.utcfromtimestamp(ts).strftime('%H:%M:%S'))


result.insert(loc=len(result.columns), column="time_diff", value=float(0.0))
result[["azim", "distance"]] = pd.DataFrame(result.apply(lambda x: azim_and_dist_from_points(x["lat_tx"], x["lon_tx"], x["lat"], x["lon"]), axis=1).tolist())

# result["df_heading_mean"] = (-result["df_angle_mean"] - result["compass_angle"]).map(lambda x: normalize_angle(x)) ########Đ
# # result["df_heading_mean"] = (-result["df_angle_mean"] + result["compass_heading"]).map(lambda x: normalize_angle(x)) # opposite rotation dir
# # result["df_heading_mean"] = (-result["df_angle_mean"] + result["compass_angle"]).map(lambda x: normalize_angle(x)) # opposite rotation dir + compass angle
# result["df_error"] = (result["df_heading_mean"] - result["azim"]).map(lambda x: normalize_angle(x))

######
# result["compass_heading"] = result["compass_angle"]
# result["df_corrected"] = (-result["df_angle"] - result["compass_angle"]).map(lambda x: normalize_angle(x))
####
if CHANGE_ROTATION_DIR:    
    result["df_heading_mean"] = (-result["df_angle_mean"] + result["compass_heading"]).map(lambda x: normalize_angle(x))
    result["df_corrected"] = (-result["df_angle"] + result["compass_heading"]).map(lambda x: normalize_angle(x))
else:
    result["df_heading_mean"] = (result["df_angle_mean"] + result["compass_heading"]).map(lambda x: normalize_angle(x)) ########Đ
    result["df_corrected"] = (result["df_angle"] + result["compass_heading"]).map(lambda x: normalize_angle(x))


result["df_error"] = (result["df_heading_mean"] - result["azim"]).map(lambda x: normalize_angle(x))

fig, ax = plt.subplots()
ax.plot(result["azim"])
# ax.plot(result["seconds"], result["azim"])

fig2, ax2 = plt.subplots()
ax2.plot(result["time_diff"])
# ax2.plot(result["seconds"], result["time_diff"])
print(result)
result.to_csv(f"{folder}{output_file}")
plt.show(block=True)