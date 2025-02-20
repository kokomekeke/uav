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

import pysagax

# import pysagax 

USE_STATIONARY_RX_COORDINATES = True
# TRANSMITTER_LAT = 47.321013 #forgato 
# TRANSMITTER_LON = 19.316929   #forgato
RECIEVER_LAT = 47.321019    #fl2
RECIEVER_LON = 19.316908    #fl2
RECIEVER_LAT = 47.320746    #fl1
RECIEVER_LON = 19.316848    #fl1
COMPASS_HEADING = 45*np.pi/180
DATE_OF_RECORDING_YMD = [2023, 11, 9]

CHANGE_ROTATION_DIR = False #false for field laptop 1 on 231109 day, true for fl2

folder = "C:\\Users\\p\\Documents\\measurments\\ocsa_231212\\"
client_data_file1 = "\\laptop1-box1\\20231212_105551.csv"
client_data_file2 = "\\laptop2-box2\\20231212_105548.csv"
gps_data_file = "20231212-105241.csv"
output_file = client_data_file1[:-4] + "_merged_trimmed_interpolated.csv"
recording_correct_first_timestamp_ns = 0 #if not 0 then the time_ns column will be shifted to start from this value (for correcting recordings made from sigmf playback) (use unix timestamp in ns!)

def normalize_angle(angle: float, high: float = np.pi, low: float = -np.pi) -> float:
    span = high - low
    while angle >= high:
        angle = angle - span
    while angle < low:
        angle = angle + span
    return angle

def read_gps_coordinates(path):
    data = pd.read_csv(path)
    str_to_timestamp = lambda time: datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp() #convert string in UTC time to timestamp
    data["time_ns_tx"] = data["date time"].map(str_to_timestamp)*1e9
    data["seconds"] = (data["time_ns_tx"] - data["time_ns_tx"][0]) / 1e9 #seconds passed since recording start (TODO: might not be needed)
    data.rename(columns={"latitude": "lat_tx", "longitude": "lon_tx"}, inplace=True)
    data.drop(["type", "name", "desc"], axis=1, inplace=True)
    return data

def azim_and_dist_from_points(lat_tx, lon_tx, lat_rx=RECIEVER_LAT, lon_rx=RECIEVER_LON):
    ##calculate gt azimuth and distance from transmitter and reciever coordinates
    result = Geodesic.WGS84.Inverse(lat_rx, lon_rx, lat_tx, lon_tx)
    azim = result["azi1"] * np.pi / 180
    dist = result["s12"]
    return azim, dist

def point_from_azims(lat1, lon1, azim1, lat2, lon2, azim2):
    pass
    return 
    return lat_tx, lon_tx, dist1, dist2

result = pd.read_csv(f"{folder}{client_data_file1}")
result["df_corrected"] = (result["df_angle"] + result["compass_heading"]).map(lambda x: pysagax.normalize_angle(x))
result.insert(loc=15, column="df_corrected_mean", value=(result["df_angle_mean"] + result["compass_heading"]).map(lambda x: pysagax.normalize_angle(x)))

measures2 = pd.read_csv(f"{folder}{client_data_file2}")
measures2["df_corrected"] = (measures2["df_angle"] + measures2["compass_heading"]).map(lambda x: pysagax.normalize_angle(x))
measures2.insert(loc=15, column="df_corrected_mean", value=(measures2["df_angle_mean"] + measures2["compass_heading"]).map(lambda x: pysagax.normalize_angle(x)))

# if recording_correct_first_timestamp_ns:
#     measures["time_ns"] = measures["time_ns"] - measures["time_ns"][0] + recording_correct_first_timestamp_ns

gt_values = read_gps_coordinates(f"{folder}{gps_data_file}")

columns = result.columns
new_column_names = {name: f"{name}_rx1" for name in columns}
new_column_names2 = {name: f"{name}_rx2" for name in columns}
result.rename(columns=new_column_names, inplace=True)
measures2.rename(columns=new_column_names2, inplace=True)

for col in measures2.columns:    
    result.insert(loc=len(result.columns), column=col, value=float("nan"))
result.insert(loc=len(result.columns), column="time_diff_rx1_rx2", value=float("nan"))

for i in range(len(measures2)):
    target_time = measures2["time_ns_rx2"][i]
    target_index = result.iloc[(result['time_ns_rx1']-target_time).abs().argsort()[:1]].index.to_list()[0]
    time_diff = (result.loc[target_index, "time_ns_rx1"]-target_time)/10**9
    if abs(result.loc[target_index, "time_diff_rx1_rx2"]) < abs(time_diff):
        continue    # skip, if we already found data with smaller time difference for this row
    result.loc[target_index, measures2.columns] = measures2.loc[i, measures2.columns]
    result.loc[target_index, "time_diff_rx1_rx2"] = time_diff
print(f"size before trim: {result.shape}")
result.dropna(subset=["time_ns_rx2"], inplace=True)
print(f"size after trim: {result.shape}")
print("done merging 1/2")

for col in gt_values.columns:    
    result.insert(loc=len(result.columns), column=col, value=float("nan"))
result.insert(loc=len(result.columns), column="time_diff_rx1_tx", value=float("nan"))
    
for i in range(len(gt_values)):
    target_time = gt_values["time_ns_tx"][i]
    target_index = result.iloc[(result['time_ns_rx1']-target_time).abs().argsort()[:1]].index.to_list()[0]
    time_diff = (result.loc[target_index, "time_ns_rx1"]-target_time)/10**9
    if abs(result.loc[target_index, "time_diff_rx1_tx"]) < abs(time_diff):
        continue    # skip, if we already found data with smaller time difference for this row
    result.loc[target_index, gt_values.columns] = gt_values.loc[i, gt_values.columns]
    result.loc[target_index, "time_diff_rx1_tx"] = time_diff


print("done merging 2/2")

result.interpolate(inplace=True) #fill in rows without matching aaronia data
# result["time_diff"] = (result["time_ns"] - result["time_ns"][0]) / 10**9 - result["seconds"]

# result[["azim", "distance"]] = pd.DataFrame(result.apply(lambda x: azim_and_dist_from_points(x["lat_tx"], x["lon_tx"], x["lat"], x["lon"]), axis=1).tolist())



# if CHANGE_ROTATION_DIR:    
#     result["df_heading_mean"] = (-result["df_angle_mean"] + result["compass_heading"]).map(lambda x: normalize_angle(x))
#     result["df_heading"] = (-result["df_angle"] + result["compass_heading"]).map(lambda x: normalize_angle(x))
# else:
#     result["df_heading_mean"] = (result["df_angle_mean"] + result["compass_heading"]).map(lambda x: normalize_angle(x)) ########Đ
#     result["df_heading"] = (result["df_angle"] + result["compass_heading"]).map(lambda x: normalize_angle(x))

# result["df_error"] = (result["df_heading_mean"] - result["azim"]).map(lambda x: normalize_angle(x))

# fig, ax = plt.subplots()
# ax.plot(result["azim"])
# ax.plot(result["seconds"], result["azim"])

fig2, ax2 = plt.subplots()
ax2.plot(result["time_diff_rx1_tx"], "r")
ax2.plot(result["time_diff_rx1_rx2"], "b")
# ax2.plot(result["seconds"], result["time_diff"])
print(result)
result.to_csv(f"{folder}{output_file}")
plt.show(block=True)