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
import pysagax 



first = last = None

#set these values for optional truncation of the dataset
first = 0
# last = 600
MAGNETIC_DECLINATION = 0# 5.65*np.pi/180

GT_CORRECTED_DF_VALUE = 218.923*np.pi/180
COMPASS_OFFSET = -2.35952710616871
ENCODER_OFFSET_FROM_MAG_NORTH = -1.21491530717959
ENCODER_OFFSET = ENCODER_OFFSET_FROM_MAG_NORTH - MAGNETIC_DECLINATION
# GT_CORRECTED_DF_VALUE = -2.3684113022222222 # =224.3°=-135.7° 

fn = sys.argv[1]
if os.path.exists(fn):
    print(os.path.basename(fn))
timestamp = re.search(r'(\d{8}_\d{6})', fn).group(1)
print("TIMESTAMP:", timestamp)

filename = "racclient_recording_20230913_153123.csv"
dataframe = pd.read_csv(fn)

if last is not None:
    dataframe = dataframe.iloc[first:last].reset_index()
    print(f"processing data from sample {first} to sample {last}\n")

print(f"compass offset: {dataframe['compass_angle'][0]}")
print(f"enc offset: {dataframe['encoder_angle'][0]}")


dataframe['compass_heading'] = -(dataframe['compass_heading'] - COMPASS_OFFSET).map(lambda x: pysagax.normalize_angle(x))
# dataframe['compass_angle'] = -dataframe['compass_angle']
dataframe['encoder_angle'] = dataframe['encoder_angle'] - ENCODER_OFFSET


# dataframe['df_corrected'] = dataframe['df_corrected'] - ENCODER_OFFSET
dataframe['df_corrected'] = dataframe['df_angle'] + dataframe["encoder_angle"]
dataframe['df_corrected_error'] = dataframe['df_corrected'] - GT_CORRECTED_DF_VALUE
dataframe['df_angle'] = -(dataframe['df_angle'] -GT_CORRECTED_DF_VALUE)#- dataframe['df_angle'][0]) #negative sign so it changes togheter with the encoder_angle for easier reading of the plots
dataframe['compass_error'] = dataframe['compass_heading'] - dataframe['encoder_angle']




mean_fn = lambda x: scipy.stats.circmean(x, high=np.pi, low=-np.pi, nan_policy="omit")

# df_value_recording = [pysagax.normalize_angle(deg) for deg in dataframe['df_angle'].rolling(100).apply(mean_fn)]
df_value_recording = [pysagax.normalize_angle(deg) for deg in dataframe['df_angle']]
df_corrected_recording = dataframe['df_corrected']# - dataframe['df_corrected'][0]
compass_heading_recording = [pysagax.normalize_angle(deg) for deg in dataframe['compass_angle']]
encoder_heading_recording = [pysagax.normalize_angle(deg) for deg in dataframe['encoder_angle']]
# df_corrected_recording = [pysagax.normalize_angle(deg) for deg in dataframe['df_corrected']]
df_corrected_recording = [pysagax.normalize_angle(deg) for deg in dataframe['df_corrected_error']]

correct_heading = 0
error_recording = [dfc - correct_heading for dfc in df_corrected_recording]

compass_error_recording = [pysagax.normalize_angle(deg) for deg in dataframe['compass_error']]

mean_error = scipy.stats.circmean(df_corrected_recording, high=np.pi, low=-np.pi, nan_policy="omit")
std_error = scipy.stats.circstd(df_corrected_recording, high=np.pi, low=-np.pi, nan_policy="omit")
rms_error = rms_error = math.sqrt(np.nanmean([error**2 for error in error_recording]))


compass_rms_error = math.sqrt(np.mean([error**2 for error in compass_error_recording]))
print(f"MEAN ERROR: \t\t{mean_error*180/np.pi:.2f}")
print(f"STD ERROR: \t\t{std_error*180/np.pi:.2f}")
print(f"RMS ERROR: \t\t{rms_error*180/np.pi:.2f}")
print(f"COMPASS RMS ERROR: \t{compass_rms_error*180/np.pi:.2f}")
print(f"COMP final val ERROR: \t{(compass_error_recording[-1] - encoder_heading_recording[-1])*180/np.pi:.2f}")



# quality_recording = dataframe['quality']
# quality_recording_deg = [180 if d is not None else None for d in df_value_recording] #TODO: better quality with separate 

df_value_recording_deg = [d * 180 / np.pi if d is not None else None for d in df_value_recording]
df_corrected_recording_deg = [d * 180 / np.pi if d is not None else None for d in df_corrected_recording]
compass_heading_recording_deg = [d * 180 / np.pi if d is not None else None for d in compass_heading_recording]
encoder_heading_recording_deg = [d * 180 / np.pi if d is not None else None for d in encoder_heading_recording]
df_elevation_recording_deg = [d * 180 / np.pi if d is not None else None for d in dataframe["df_elevation"]]

compass_error_recording_deg = [d * 180 / np.pi if d is not None else None for d in compass_error_recording]

angle_fig, angle_ax = plt.subplots()
compass_fig, compass_ax = plt.subplots()
time_fig, time_ax = plt.subplots()
peak_ax = time_ax.twinx()

# plt.title("asdf")
angle_ax.plot(encoder_heading_recording_deg, df_value_recording_deg, color="green", label="encoder-DF")
angle_ax.legend()
angle_ax.grid(visible=True)
angle_ax.set_ylabel("DF angle")
angle_ax.set_xlabel("Encoder angle")
angle_ax.set_xlim(-180, 180)
angle_ax.set_ylim(-180, 180)
angle_ax.plot([-180, 180], [-180, 180], color="gray", linewidth=1, alpha=0.5)
angle_ax.plot([-180, 180], [180, -180], color="gray", linewidth=1, alpha=0.5)

compass_ax.plot(encoder_heading_recording_deg, compass_heading_recording_deg, color="pink", label="encoder-compass(sensorfusion)")
compass_ax.plot(encoder_heading_recording_deg, dataframe["compass_heading"]*180/np.pi, color="red", label="encoder-compass(magnetometer)")
compass_ax.legend()
compass_ax.grid(visible=True)
compass_ax.set_ylabel("Compass angle")
compass_ax.set_xlabel("Encoder angle")
compass_ax.set_xlim(-180, 180)
compass_ax.set_ylim(-180, 180)
compass_ax.plot([-180, 180], [-180, 180], color="gray", linewidth=1, alpha=0.5)
compass_ax.plot([-180, 180], [180, -180], color="gray", linewidth=1, alpha=0.5)

time_ax.plot(df_value_recording_deg, color="blue", label="DF angle")
time_ax.plot(df_elevation_recording_deg, color="pink", label="DF elevation")
time_ax.plot(df_corrected_recording_deg, color="cyan", label="DF corrected error")
# time_ax.plot(compass_heading_recording_deg, color="pink", label="compass")
# time_ax.plot(-dataframe["compass_heading"]*180/np.pi, color="red", label="compass")
time_ax.plot(encoder_heading_recording_deg, color="green", label="encoder")
# time_ax.plot(compass_error_recording_deg, color="black", label="eder")
time_ax.grid(visible=True)
time_ax.set_ylabel("Angle")
time_ax.set_xlabel("Sample")
time_ax.set_ylim(-180, 180)


#PEAK chart
dataframe["maxpeak"] = dataframe[["peak0", "peak1", "peak2", "peak3"]].max(axis=1)
dataframe["minpeak"] = dataframe[["peak0", "peak1", "peak2", "peak3"]].min(axis=1)
dataframe['maxpeak2'] = dataframe['maxpeak'].rolling(15, center=True).max()
dataframe['minpeak2'] = dataframe['minpeak'].rolling(15, center=True).min()

adc_resolution = 2**15 - 1
dataframe['maxpeak2'] = dataframe['maxpeak2'].map(lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else float("-inf"))
dataframe['minpeak2'] = dataframe['minpeak2'].map(lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else float("-inf"))
min_dbfs_level = 20 * math.log10(400 / adc_resolution)

# peak_ax.fill_between(x=dataframe.index.to_list(),y1=dataframe["maxpeak"], y2=dataframe["minpeak"], color="red", alpha=0.5, linestyle="None", linewidth=0)
peak_ax.fill_between(x=dataframe.index.to_list(),y1=dataframe["maxpeak2"], y2=dataframe["minpeak2"], color="black", alpha=0.2, linestyle="None", linewidth=0, label="peak dBFS")
peak_ax.set_ylim(min_dbfs_level, 0)
peak_ax.set_ylabel("peak dBFS")

time_fig.legend(loc="upper center", ncols=3)
# peak_ax.plot(dataframe["peak0"])
# peak_ax.plot(dataframe["peak1"])
# peak_ax.plot(dataframe["peak2"])
# peak_ax.plot(dataframe["peak3"])
# peak_ax.plot(dataframe["maxpeak"])
# peak_ax.plot(dataframe["minpeak"])
angle_fig.show()
compass_fig.show()
time_fig.show()

dpi = 300

angle_fig.savefig(f"angle_{timestamp}.png", dpi=dpi)
compass_fig.savefig(f"compass_{timestamp}.png", dpi=dpi)
time_fig.savefig(f"time_{timestamp}.png", dpi=dpi)

f = open(f"info_{timestamp}.txt", "w")
f.write(f"MAGNETIC_DECLINATION: \t\t{MAGNETIC_DECLINATION*180/np.pi}\n"
        f"GT_CORRECTED_DF_VALUE: \t\t{GT_CORRECTED_DF_VALUE*180/np.pi}\n"
        f"COMPASS_OFFSET = \t\t{COMPASS_OFFSET*180/np.pi}\n"
        f"ENCODER_OFFSET_FROM_MAG_NORTH = {ENCODER_OFFSET_FROM_MAG_NORTH*180/np.pi}\n"
        f"ENCODER_OFFSET = \t\t{ENCODER_OFFSET*180/np.pi}\n"
        f"\n"
        f"MEAN ERROR: \t\t{mean_error*180/np.pi:.2f}°\n"
        f"STD ERROR: \t\t{std_error*180/np.pi:.2f}°\n"
        f"RMS ERROR: \t\t{rms_error*180/np.pi:.2f}°\n"
        f"COMPASS RMS ERROR: \t{compass_rms_error*180/np.pi:.2f}°\n"
        f"COMP final val ERROR: \t{(compass_error_recording[-1] - encoder_heading_recording[-1])*180/np.pi:.2f}°\n"
        )
f.close()

plt.show(block=True)    

# plt.savefig(fname="asd.png", dpi=100)


# print("asd")