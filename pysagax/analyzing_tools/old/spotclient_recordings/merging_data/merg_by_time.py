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

from pysagax import normalize_angle

# import pysagax 

USE_STATIONARY_RX_COORDINATES = False
# TRANSMITTER_LAT = 47.321013 #forgato 
# TRANSMITTER_LON = 19.316929   #forgato
RECIEVER_LAT = 47.321019    #fl2
RECIEVER_LON = 19.316908    #fl2
RECIEVER_LAT = 47.320746    #fl1
RECIEVER_LON = 19.316848    #fl1
COMPASS_HEADING = 45*np.pi/180
DATE_OF_RECORDING_YMD = [2023, 11, 9]

CHANGE_ROTATION_DIR = True #false for field laptop 1 on 231109 day, true for fl2

folder = "C:\\Users\\p\\Documents\\measurments\\ocsa_231212\\"
client_data_file = "\\laptop1-box1\\20231212_105551.csv"
# client_data_file = "\\laptop2-box2\\20231212_105548.csv"
aaronia_data_file = "20231212-105241.csv"
output_file = client_data_file[:-4] + "_merged2r.csv"
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

def read_aaronia_coordinates(path):
    gps_pattern = re.compile(
        r"\$GPGGA,(\d{6})\.(\d*),(\d*)(\d{2}\.\d*)?,([NS]?),(\d*)(\d{2}\.\d*)?,([EW]?),"
        r"([01]),(\d*),([\d.]*),([\d.]*),([A-Z]*),([\d.]*),([A-Z]*),[a-zA-Z0-9]*,[a-zA-Z0-9]*.*\*([0-9A-F]{2})"
    )
    data = {"seconds": [],
            "time": [],
            "time_ns_tx": [],
            "lat_tx": [],
            "lon_tx": []}
    file = open(path, "r")
    for line in file.readlines():
        tokens = gps_pattern.match(line)
        if tokens is not None:
            data_hms = [
                int(tokens[1][0:2]),
                int(tokens[1][2:4]),
                int(tokens[1][4:6]),
              ]  # original timestamp is HHMMSS format
            seconds = (
                    data_hms[0] * 3600 + data_hms[1] * 60 + data_hms[2]
            )  # Timestamp is converted to total seconds
            data_idx = int(tokens[2])
            data_ok = int(tokens[9])
            if data_ok:
                lat_deg = int(tokens[3])
                lat_min = float(tokens[4])
                lat_hem = tokens[5]
                lon_deg = int(tokens[6])
                lon_min = float(tokens[7])
                lon_hem = tokens[8]
                lat_tx = (1 if lat_hem == "N" else -1) * (lat_deg + lat_min / 60)
                lon_tx = (1 if lon_hem == "E" else -1) * (lon_deg + lon_min / 60)
                number_of_satellites = int(tokens[10])
                horizontal_deviation = float(tokens[11])
                elevation = float(tokens[12])
                elevation_units = tokens[13]
                geoidal_separation = float(tokens[14])
                geoidal_separation_units = tokens[15]

                aaroia_time_ns = datetime.datetime(*(DATE_OF_RECORDING_YMD + data_hms), tzinfo=datetime.timezone.utc).timestamp()*1e9

                data["seconds"].append(seconds)
                data["time"].append(f"{data_hms[0]:02d}:{data_hms[1]:02d}:{data_hms[2]:02d}")
                data["time_ns_tx"].append(aaroia_time_ns)
                data["lat_tx"].append(lat_tx)
                data["lon_tx"].append(lon_tx)

    recording_start_second = data["seconds"][0]
    data["seconds"] = [d - recording_start_second for d in data["seconds"]] ##start seconds column from 0
    
    dataframe = pd.DataFrame(data)
    return dataframe

def azim_and_dist_from_points(lat_tx, lon_tx, lat_rx=RECIEVER_LAT, lon_rx=RECIEVER_LON):
    ##calculate gt azimuth and distance from transmitter and reciever coordinates
    result = Geodesic.WGS84.Inverse(lat_rx, lon_rx, lat_tx, lon_tx)
    azim = result["azi1"] * np.pi / 180
    dist = result["s12"]
    return azim, dist

measures = pd.read_csv(f"{folder}{client_data_file}")

if recording_correct_first_timestamp_ns:
    measures["time_ns"] = measures["time_ns"] - measures["time_ns"][0] + recording_correct_first_timestamp_ns

result = measures

result["df_corrected"] = (result["df_angle"] + result["compass_heading"]).map(lambda x: normalize_angle(x))
result.insert(loc=15, column="df_corrected_mean", value=(result["df_angle_mean"] + result["compass_heading"]).map(lambda x: normalize_angle(x)))

gt_values = read_gps_coordinates(f"{folder}{aaronia_data_file}")
for col in gt_values.columns:    
    result.insert(loc=len(result.columns), column=col, value=float("nan"))
result.insert(loc=len(result.columns), column="time_diff", value=float("nan"))

# result.insert(loc=len(result.columns), column="seconds", value=float("nan"))
# result.insert(loc=len(result.columns), column="time", value=float("nan"))
# result.insert(loc=len(result.columns), column="lat_tx", value=float("nan"))
# result.insert(loc=len(result.columns), column="lon_tx", value=float("nan"))
# result.insert(loc=len(result.columns), column="time_diff", value=float("nan"))
# result.insert(loc=len(result.columns), column="DFMean", value=float("nan"))
# result.insert(loc=len(result.columns), column="DFDeviation", value=float("nan"))
# result.insert(loc=len(result.columns), column="DFError", value=float("nan"))
# print(result[["Seconds","Time","Lat","Lon","Azim","Distance","DFMean","DFMean","DFDeviation","DFError"]].iloc[int(5)])
# print(gt_values)
# print(gt_values[["Seconds","Time","Lat","Lon","Azim","Distance","DFMean","DFMean","DFDeviation","DFError"]].iloc[1])

for i in range(len(gt_values)):

    # target_time = result["time_ns"][0] + gt_values["seconds"][i]*10**9 # Calculate matching row by elapsed time since the start of client recordings and aaronia logs
    target_time = gt_values["time_ns_tx"][i] # calculate matching rows from unix timestamps
    
    target_index = result.iloc[(result['time_ns']-target_time).abs().argsort()[:1]].index.to_list()[0]
    time_diff = (result.loc[target_index, "time_ns"]-target_time)/10**9
    if abs(result.loc[target_index, "time_diff"]) < abs(time_diff):
        continue    # skip, if we already found aaronia data with smaller time difference for this row
    
    result.loc[target_index, gt_values.columns] = gt_values.loc[i, gt_values.columns]
    result.loc[target_index, "time_diff"] = time_diff
result.interpolate(inplace=True) #fill in rows without matching aaronia data
# result["time_diff"] = (result["time_ns"] - result["time_ns"][0]) / 10**9 - result["seconds"]

if USE_STATIONARY_RX_COORDINATES:
    result["lat"] = RECIEVER_LAT
    result["lon"] = RECIEVER_LON
    result["compass_angle"] = COMPASS_HEADING
    result["compass_heading"] = COMPASS_HEADING

result[["azim", "distance"]] = pd.DataFrame(result.apply(lambda x: azim_and_dist_from_points(x["lat_tx"], x["lon_tx"], x["lat"], x["lon"]), axis=1).tolist())



if CHANGE_ROTATION_DIR:    
    result["df_corrected_mean"] = (-result["df_angle_mean"] + result["compass_heading"]).map(lambda x: normalize_angle(x))
    result["df_corrected"] = (-result["df_angle"] + result["compass_heading"]).map(lambda x: normalize_angle(x))
else:
    result["df_corrected_mean"] = (result["df_angle_mean"] + result["compass_heading"]).map(lambda x: normalize_angle(x)) ########Đ
    result["df_corrected"] = (result["df_angle"] + result["compass_heading"]).map(lambda x: normalize_angle(x))

result["df_error"] = (result["df_corrected_mean"] - result["azim"]).map(lambda x: normalize_angle(x))

fig, ax = plt.subplots()
ax.plot(result["azim"])
# ax.plot(result["seconds"], result["azim"])

fig2, ax2 = plt.subplots()
ax2.plot(result["time_diff"])
# ax2.plot(result["seconds"], result["time_diff"])
print(result)
result.to_csv(f"{folder}{output_file}")
plt.show(block=True)