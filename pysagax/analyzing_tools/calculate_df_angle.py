"""
GUI program for calculating the correct DF angle of a known transmitter.
CURRENTLY IT DOESN'T COMPENSATE WITH AIRCRAFT PITCH AND ROLL!
TODO: I should finish this

The file contains useful code for implementing the final heading compensation in PysagaxUAV
"""


import tkinter as tk
from tkinter import ttk
import numpy as np

def calculate():
    result = calculate_df_angle(
        float(target_lat_entry.get()),
        float(target_lon_entry.get()),
        float(drone_lat_entry.get()),
        float(drone_lon_entry.get()),
        float(altitude_entry.get()),
        float(yaw_entry.get()),
        float(pitch_entry.get()),
        float(roll_entry.get())
    )
    result_label.config(text=f"Result: WATCH, RESULTS ARE NOT YET CORRECT, FINISH calculate_df_angle() function{result}")


def azim_and_dist_from_points(lat_tx, lon_tx, lat_rx, lon_rx):
    """copied from merge_stationary_transmitter.py"""
    ##calculate gt azimuth and distance from transmitter and reciever coordinates
    import scipy
    from geographiclib.geodesic import Geodesic

    result = Geodesic.WGS84.Inverse(lat_rx, lon_rx, lat_tx, lon_tx)
    # print(result)
    azim = result["azi1"] * np.pi / 180 #TODO: is this radians or degrees??????
    dist = result["s12"]
    return azim, dist

def calculate_df_angle(target_lat, target_lon, drone_lat, drone_lon, altitude, yaw, pitch, roll):

    distance = 0
    azimuth = 0

    azimuth, distance = azim_and_dist_from_points(target_lat, target_lon, drone_lat, drone_lon)
    return azimuth*180/np.pi, distance

root = tk.Tk()
root.title("DF Angle Calculation")

ttk.Label(root, text="Target Latitude:").grid(row=0, column=0, padx=5, pady=5)
target_lat_entry = ttk.Entry(root)
target_lat_entry.grid(row=0, column=1, padx=5, pady=5)

ttk.Label(root, text="Target Longitude:").grid(row=1, column=0, padx=5, pady=5)
target_lon_entry = ttk.Entry(root)
target_lon_entry.grid(row=1, column=1, padx=5, pady=5)

ttk.Label(root, text="Drone Latitude:").grid(row=2, column=0, padx=5, pady=5)
drone_lat_entry = ttk.Entry(root)
drone_lat_entry.grid(row=2, column=1, padx=5, pady=5)

ttk.Label(root, text="Drone Longitude:").grid(row=3, column=0, padx=5, pady=5)
drone_lon_entry = ttk.Entry(root)
drone_lon_entry.grid(row=3, column=1, padx=5, pady=5)

ttk.Label(root, text="Altitude:").grid(row=4, column=0, padx=5, pady=5)
altitude_entry = ttk.Entry(root)
altitude_entry.grid(row=4, column=1, padx=5, pady=5)

ttk.Label(root, text="Yaw:").grid(row=5, column=0, padx=5, pady=5)
yaw_entry = ttk.Entry(root)
yaw_entry.grid(row=5, column=1, padx=5, pady=5)

ttk.Label(root, text="Pitch:").grid(row=6, column=0, padx=5, pady=5)
pitch_entry = ttk.Entry(root)
pitch_entry.grid(row=6, column=1, padx=5, pady=5)

ttk.Label(root, text="Roll:").grid(row=7, column=0, padx=5, pady=5)
roll_entry = ttk.Entry(root)
roll_entry.grid(row=7, column=1, padx=5, pady=5)

calculate_button = ttk.Button(root, text="Calculate", command=calculate)
calculate_button.grid(row=8, column=0, columnspan=2, pady=10)

result_label = ttk.Label(root, text="Result: ")
result_label.grid(row=9, column=0, columnspan=2, pady=5)

root.mainloop()
