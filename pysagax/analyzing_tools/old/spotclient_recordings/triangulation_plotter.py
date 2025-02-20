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
first = 289
# last = -1

plot_type = 3 #0: complex; 1: driving; 2: running; 3: runtime aggregated results (with trimming), 4: runtime aggregated results (wo trimming)



def create_angle_plot(xlabel, ylabel, angle_angle=False):
    plot_degree_tick_location = np.arange(-180, 181, 30) 
    plot_degree_tick_str = [f"{i}°" for i in np.arange(-180, 181, 30)]

    fig, ax = plt.subplots(figsize=(19.20,10.80))
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    ax.set_ylim(-180, 180)   
    ax.set_yticks(plot_degree_tick_location, plot_degree_tick_str)
    if angle_angle:
        ax.plot([-180, 180], [-180, 180], color="gray", linewidth=1, alpha=0.5)
        ax.plot([-180, 180], [180, -180], color="gray", linewidth=1, alpha=0.5)
        ax.set_xlim(-180, 180)
        ax.set_xticks(plot_degree_tick_location, plot_degree_tick_str)
    ax.grid(visible=True)
    return fig, ax

fn = sys.argv[1]
if os.path.exists(fn):
    print(os.path.basename(fn))

dataframe = pd.read_csv(fn)
def insert_empty_rows(df, dt):
    columns = df.columns
    new_rows = []
    for i in range(len(df) - 1):
        new_rows.append(df.iloc[i])
        time_diff = df['seconds'].iloc[i + 1] - df['seconds'].iloc[i]
        if time_diff > 1:
            empty_row = pd.Series({col: np.nan for col in columns})
            new_rows.append(empty_row)
    new_rows.append(df.iloc[-1])
    new_df = pd.DataFrame(new_rows, columns=columns)
    return new_df
#insert empyty rows between consecutive datapoints more than 10 seconds apart 
#so that they aren't connected on the final plots
dataframe = insert_empty_rows(dataframe, 10) 


if last is not None:
    dataframe = dataframe.iloc[first:last].reset_index()
    print(f"processing data from sample {first} to sample {last}\n")

print(f"compass offset: {dataframe['compass_angle'][0]}")
print(f"enc offset: {dataframe['encoder_angle'][0]}")


# dataframe["azim"] = dataframe["azim"].map(lambda x: pysagax.normalize_angle(x/180*np.pi))
if "quality" not in dataframe.columns:
    dataframe["quality"] = None
    print("Empty queality column added to dataframe")

mean_fn = lambda x: scipy.stats.circmean(x, high=np.pi, low=-np.pi, nan_policy="omit")

def circmedian(angs):
    pdists = angs[np.newaxis, :] - angs[:, np.newaxis]
    pdists = (pdists + np.pi) % (2 * np.pi) - np.pi
    pdists = np.abs(pdists).sum(1)
    return angs[np.argmin(pdists)]

print("A")
med_fn = lambda x: circmedian(x.values)



def plot_angles(x, column: pd.Series, window_size, aggregating_fn, name, xlabel="Samples", variance_over_line=False, plot_peaks=True, plot_dist=True, plot_quality=False, plot_df_angle=False, angle_vars=None):
    
    angles_aggregated_deg = (column.rolling(window_size).apply(aggregating_fn) - dataframe["azim"]).map(lambda x: pysagax.normalize_angle(x)*180/np.pi)
    
    time_fig, time_ax = create_angle_plot(xlabel, "Angle (deg)", False)
    ##TODO: use create_angle_plot here as well?
    # time_fig, (quality_ax, time_ax) = plt.subplots(nrows=2, sharex=True, height_ratios=[1,5], figsize=(19.20,10.80))

    time_ax.plot(x, angles_aggregated_deg, color="blue", label=f"{name} error")
    # time_ax.plot(x, dataframe["compass_heading"]*180/np.pi, color="green", label=f"compass")
    # time_ax.plot(x, dataframe["compass_angle"]*180/np.pi, color="brown", label=f"compass")
    # time_ax.plot(x, (column - dataframe["compass_angle"]).map(lambda x: pysagax.normalize_angle(x))*180/np.pi, color="purple", label=f"uncompensated df_azim")
    time_ax.plot(x, dataframe["azim"]*180/np.pi, color="green", label="correct azim", zorder=10, linewidth=4)

    dev_fn = lambda x: scipy.stats.circvar(x, high=np.pi, low=-np.pi, nan_policy="omit")/2
    if angle_vars is None:
        angle_vars = (column.rolling(window_size).apply(dev_fn)*180/np.pi)
    else:
        angle_vars = angle_vars * 180 / np.pi
    if plot_df_angle:
        df_angle_avg = (column.rolling(window_size).apply(aggregating_fn)).map(lambda x: pysagax.normalize_angle(x)*180/np.pi)
        time_ax.plot(x, df_angle_avg, color="red", label=f"{name}")
        if variance_over_line:
            dev_top = (df_angle_avg + angle_vars)#.map(lambda x: pysagax.normalize_angle(x)*180/np.pi)
            dev_bot = (df_angle_avg - angle_vars)

        
        angle_fig, angle_ax = create_angle_plot("correct angle", name, True)
        angle_ax.plot(dataframe["azim"]*180/np.pi, df_angle_avg, color="green", label=f"{name} - correct azimuth")
        angle_ax.legend()
        angle_fig.savefig(f"{name}_angle.png", dpi=500,)
    if not variance_over_line or not plot_df_angle:
        dev_top = angle_vars#.map(lambda x: pysagax.normalize_angle(x)*180/np.pi)
        dev_bot = - angle_vars#.map(lambda x: pysagax.normalize_angle(x)*180/np.pi)
    
    time_ax.fill_between(x=x, y1=dev_top, y2=dev_bot, color="red", alpha=0.3, linestyle="None", linewidth=0, label="df angle variance")



    if plot_peaks:
        #PEAK chart
        peak_df = dataframe[["peak0", "peak1", "peak2", "peak3"]]
        peak_df["maxpeak"] = peak_df[["peak0", "peak1", "peak2", "peak3"]].max(axis=1)
        peak_df["minpeak"] = peak_df[["peak0", "peak1", "peak2", "peak3"]].min(axis=1)
        peak_df['maxpeak2'] = peak_df['maxpeak'].rolling(1, center=True).max()
        peak_df['minpeak2'] = peak_df['minpeak'].rolling(1, center=True).min()
        adc_resolution = 2**15 - 1
        peak_df['maxpeak2'] = peak_df['maxpeak2'].map(lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000)
        peak_df['minpeak2'] = peak_df['minpeak2'].map(lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000)
        peak_df['minpeak2'] = peak_df['minpeak2'].map(lambda x: -1 if x > -1 else x)   #make the peak band visible if all channels have full scale peak values
        min_dbfs_level = 20 * math.log10(400 / adc_resolution)
        # peak_ax.fill_between(x=dataframe.index.to_list(),y1=dataframe["maxpeak"], y2=dataframe["minpeak"], color="red", alpha=0.5, linestyle="None", linewidth=0)
        peak_ax = time_ax.twinx()
        peak_ax.fill_between(x=x, y1=peak_df["maxpeak2"], y2=peak_df["minpeak2"], color="black", alpha=0.2, linestyle="None", linewidth=0, label="peak dBFS")
        peak_ax.set_ylim(min_dbfs_level, 0)
        peak_ax.set_ylabel("peak dBFS")
    # if plot_peaks:
    #     #PEAK chart
    #     print( dataframe[["peak0", "peak1", "peak2", "peak3"]])
    #     print("MAX", dataframe[["peak0", "peak1", "peak2", "peak3"]].max(axis=1))
    #     maxpeak = dataframe[["peak0", "peak1", "peak2", "peak3"]].max(axis=1)
    #     minpeak = dataframe[["peak0", "peak1", "peak2", "peak3"]].min(axis=1)
    #     maxpeak2 = maxpeak.rolling(15, center=True).max()
    #     minpeak2 = minpeak.rolling(15, center=True).min()

    #     adc_resolution = 2**15 - 1
    #     maxpeak2 = maxpeak2.map(lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000)
    #     minpeak2 = minpeak2.map(lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000)
    #     min_dbfs_level = 20 * math.log10(400 / adc_resolution)

    #     # peak_ax.fill_between(x=dataframe.index.to_list(),y1=dataframe["maxpeak"], y2=dataframe["minpeak"], color="red", alpha=0.5, linestyle="None", linewidth=0)
    #     peak_ax = time_ax.twinx()
    #     peak_ax.fill_between(x=x, y1=maxpeak2, y2=minpeak2, color="black", alpha=0.2, linestyle="None", linewidth=0, label="peak dBFS")
    #     peak_ax.set_ylim(min_dbfs_level, 0)
    #     print("MAXPEAK", maxpeak2)
    #     print("MINPEAK", minpeak2)
    #     peak_ax.set_ylabel("peak dBFS")
    
    if plot_dist:
        dist_ax = time_ax.twinx()
        dist_ax.spines['right'].set_position(('outward', 60))
        dist_ax.plot(x, dataframe["distance"], color="black", label="distance")
        dist_ax.set_ylabel("distance (m)")

    # time_ax.plot(dataframe["df_elevation"]*180/np.pi, color="pink", label="DF elevation", zorder=0)
    time_fig.legend(loc="upper center", ncols=4)
    time_fig.savefig(f"{name}.png", dpi=500,)# papertype="a3")
    time_fig.show()

    if plot_quality:
        quality_fig, quality_ax = plt.subplots(figsize=(19.20,10.80))
        quality_ax.plot(x, dataframe["quality"], "o", markersize=1, color="orange", label="quality")
        avg_fn = lambda x: sum(x)/len(x)
        quality_ax.plot(x, dataframe["quality"].rolling(window_size).apply(avg_fn), color="red", label="quality_avg")
        quality_ax.set_ylabel(f"quality{window_size}")
        quality_ax.set_ylim(0,1)
        quality_fig.legend(loc="upper center", ncols=3)
        quality_fig.savefig(f"{name}_quality.png", dpi=500,)# papertype="a3")
        quality_fig.show()

x_values = dataframe.index.to_list()
x_values = dataframe["seconds"]

original_dataframe = dataframe

if plot_type == 0:
    ###COMPLEX PLOTS
    plot_angles(x_values, dataframe["df_angle"], 10, med_fn, "median azim error 10", "Time (s)")
    plot_angles(x_values, dataframe["df_angle"], 100, med_fn, "2median azim error 100", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True)
    plot_angles(x_values, dataframe["df_angle"], 1000, med_fn, "median azim error 1000", "Time (s)")
    plot_angles(x_values, dataframe["df_angle"], 10, mean_fn, "mean azim error 10", "Time (s)")
    plot_angles(x_values, dataframe["df_angle"], 100, mean_fn, "mean azim error 100", "Time (s)")
    plot_angles(x_values, dataframe["df_angle"], 1000, mean_fn, "mean azim error 1000", "Time (s)")

    plot_angles(x_values, dataframe["df_angle"], 10, med_fn, "median azim error 10", "Time (s)")
    plot_angles(x_values, dataframe["df_angle"], 100, med_fn, "median azim error 100", "Time (s)")
    plot_angles(x_values, dataframe["df_angle"], 1, med_fn, "azim error 1", "Time (s)")
    plot_angles(x_values, dataframe["df_angle"], 10, mean_fn, "mean azim error 10", "Time (s)")
    plot_angles(x_values, dataframe["df_angle"], 100, mean_fn, "mean azim error 100", "Time (s)")

elif plot_type == 1:
    ###DRIVING PLOTS (ideal for longer recordings)
    plot_angles(x_values, dataframe["df_angle"], 10, med_fn, "median(10) azim", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=False)
    plot_angles(x_values, dataframe["df_angle"], 100, med_fn, "median(100) azim", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=False)
    plot_angles(x_values, dataframe["df_angle"], 10, med_fn, "mean(10) azim", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=False)
    plot_angles(x_values, dataframe["df_angle"], 100, med_fn, "mean(100) azim", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=False)

elif plot_type == 2:
    ###RUNNING PLOTS (ideal for shorter recordings)
    plot_angles(x_values, dataframe["df_angle"], 1, med_fn, "median(1) azim", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=False)
    plot_angles(x_values, dataframe["df_angle"], 10, med_fn, "median(10) azim", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=False)
    plot_angles(x_values, dataframe["df_angle"], 1, med_fn, "mean(1) azim", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=False)
    plot_angles(x_values, dataframe["df_angle"], 10, med_fn, "mean(10) azim", "Time (s)", plot_quality=True, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=False)

elif plot_type == 3:
    ###FOR DATA WITH RUNTIUME AGGREGATION
    dataframe["keep_rows"] = dataframe["df_angle_mean"].diff()
    dataframe["keep_rows"][0] = 1
    dataframe = dataframe[dataframe["keep_rows"] != 0]
    x_values = dataframe["seconds"]
    dataframe["df_angle"] = dataframe["df_heading_mean"]
    # dataframe["df_heading"] = (dataframe["df_angle"] + dataframe["compass_angle"]).map(lambda x: pysagax.normalize_angle(x))
    plot_angles(x_values, dataframe["df_angle"], 1, med_fn, "mean azim", "Time (s)", plot_quality=False, plot_dist=False, variance_over_line=True, plot_df_angle=True, plot_peaks=True, angle_vars=dataframe["df_angle_std"])
elif plot_type == 4:
    # dataframe["keep_rows"] = dataframe["df_angle_mean"].diff()
    # dataframe["keep_rows"][0] = 1
    # dataframe = dataframe[dataframe["keep_rows"] != 0]
    # x_values = dataframe["seconds"]
    # dataframe["df_angle"] = dataframe["df_angle_mean"]
    dataframe.insert(loc=len(dataframe.columns), column="df_angle_std", value=0)
    plot_angles(x_values, dataframe["df_angle"], 1, med_fn, "mean azim", "Time (s)", plot_quality=True, plot_dist=True, variance_over_line=True, plot_df_angle=True, plot_peaks=False, angle_vars=dataframe["df_angle_std"])

dataframe = original_dataframe
""" 

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
 """
""" angle_fig, angle_ax = plt.subplots()
compass_fig, compass_ax = plt.subplots()
 """



""" 
angle_ax.plot(encoder_heading_recording_deg, df_value_recording_deg, color="green", label="encoder-DF")
angle_ax.legend()
angle_ax.grid(visible=True)
angle_ax.set_ylabel("DF angle")
angle_ax.set_xlabel("Encoder angle")
angle_ax.set_xlim(-180, 180)
angle_ax.set_ylim(-180, 180)
angle_ax.plot([-180, 180], [-180, 180], color="gray", linewidth=1, alpha=0.5)
angle_ax.plot([-180, 180], [180, -180], color="gray", linewidth=1, alpha=0.5)

compass_ax.plot(encoder_heading_recording_deg, compass_heading_recording_deg, color="red", label="encoder-compass")
compass_ax.legend()
compass_ax.grid(visible=True)
compass_ax.set_ylabel("Compass angle")
compass_ax.set_xlabel("Encoder angle")
compass_ax.set_xlim(-180, 180)
compass_ax.set_ylim(-180, 180)
compass_ax.plot([-180, 180], [-180, 180], color="gray", linewidth=1, alpha=0.5)
compass_ax.plot([-180, 180], [180, -180], color="gray", linewidth=1, alpha=0.5)
 """


df_fig, df_ax = plt.subplots(figsize=(19.20,10.80))
df_ax.plot(dataframe["seconds"],dataframe["df_heading"]*180/np.pi, "bo", markersize=3, label="df_heading")
# df_ax.plot(dataframe["seconds"], (-dataframe["df_angle"] + dataframe["compass_angle"]).apply(lambda x: pysagax.normalize_angle(x)*180/np.pi), "bo", markersize=3, label="df_heading")
df_ax.plot(dataframe["seconds"], dataframe["azim"]*180/np.pi, color="green", label="correct azim", zorder=10,  linewidth=4)
if plot_type == 2:
    #running
    df_ax.plot(dataframe["seconds"], (dataframe["df_angle_mean"].rolling(10).apply(med_fn)).map(lambda x: pysagax.normalize_angle(x))*180/np.pi, "g", label="df_median10")
elif plot_type == 3 or plot_type == 4:
    df_ax.plot(dataframe["seconds"], dataframe["df_heading_mean"]*180/np.pi, "r", label="mean azimuth")
    pass
else:
    df_ax.plot(dataframe["seconds"], (dataframe["df_angle"].rolling(100).apply(med_fn)).map(lambda x: pysagax.normalize_angle(x))*180/np.pi, "g", label="df_median100")

df_ax.set_yticks(np.arange(-180, 181, 30), [f"{i}°" for i in np.arange(-180, 181, 30)])
df_ax.grid(visible=True)
df_ax.set_ylabel("Angle (deg)")
df_ax.set_xlabel("Time (s)")
df_ax.set_ylim(-180, 180)

df_fig.legend(loc="upper center", ncols=3)
df_fig.show()

dpi = 500

# angle_fig.savefig(f"angle_{timestamp}.png", dpi=dpi)
# compass_fig.savefig(f"compass_{timestamp}.png", dpi=dpi)
# time_fig.savefig(f"time_{timestamp}.png", dpi=dpi)

df_fig.savefig(f"samples_vs_median.png", dpi=500,)# papertype="a3")
print("FINISHED")

df_heading_error = dataframe["df_heading"] - dataframe["azim"]
df_aggregated_heading_error = dataframe["df_heading_mean"] - dataframe["azim"]

std_error = scipy.stats.circstd(df_heading_error, high=np.pi, low=-np.pi, nan_policy="omit")
rms_error = rms_error = math.sqrt(np.nanmean([error**2 for error in df_heading_error]))
aggregated_std_error = scipy.stats.circstd(df_aggregated_heading_error, high=np.pi, low=-np.pi, nan_policy="omit")
aggregated_rms_error = rms_error = math.sqrt(np.nanmean([error**2 for error in df_aggregated_heading_error]))

print("ERROR for individual df_values:")
print(f"\tSTD ERROR:\t{std_error*180/np.pi:.2f}")
print(f"\tRMS ERROR:\t{rms_error*180/np.pi:.2f}")
print("ERROR for aggregated df_values:")
print(f"\tSTD ERROR:\t{aggregated_std_error*180/np.pi:.2f}")
print(f"\tRMS ERROR:\t{aggregated_rms_error*180/np.pi:.2f}")


f = open(f"stats.txt", "w")
f.write(f"ERROR for individual df_values:\n"
        f"\tSTD ERROR:\t{std_error*180/np.pi:.2f}\n"
        f"\tRMS ERROR:\t{rms_error*180/np.pi:.2f}\n"
        f"ERROR for aggregated df_values:\n"
        f"\tSTD ERROR:\t{aggregated_std_error*180/np.pi:.2f}\n"
        f"\tRMS ERROR:\t{aggregated_rms_error*180/np.pi:.2f}\n"
        )
f.close()









plt.show(block=True)    

# plt.savefig(fname="asd.png", dpi=100)

