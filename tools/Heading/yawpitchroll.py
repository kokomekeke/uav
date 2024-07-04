"""
GUI program for calculating the error for geolocating with heading (yaw) instead of 
using aircraft attitude (yaw-pitch-roll) compensated DF angles.

The file contains useful code for implementing the final heading compensation in PysagaxUAV
"""

import tkinter as tk
from scipy.spatial.transform import Rotation
from pysagax.util.mat import normalize_angle
import numpy as np 
 

class HeadingCalculator(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Heading Error Calculator")

        self.yaw = tk.DoubleVar()
        self.pitch = tk.DoubleVar()
        self.roll = tk.DoubleVar()
        self.x = tk.DoubleVar()
        self.y = tk.DoubleVar()
        self.z = tk.DoubleVar()

        self.create_widgets()

    def create_widgets(self):
        # Slider for yaw angle
        yaw_slider = tk.Scale(self, from_=-180, to=180, orient=tk.HORIZONTAL, label="Yaw (degrees)",
                              variable=self.yaw, command=self.update_quaternion, length=300)
        yaw_slider.pack()

        # Slider for pitch angle
        pitch_slider = tk.Scale(self, from_=-90, to=90, orient=tk.HORIZONTAL, label="Pitch (degrees)",
                                variable=self.pitch, command=self.update_quaternion, length=300)
        pitch_slider.pack()

        # Slider for roll angle
        roll_slider = tk.Scale(self, from_=-180, to=180, orient=tk.HORIZONTAL, label="Roll (degrees)",
                               variable=self.roll, command=self.update_quaternion, length=300)
        roll_slider.pack()

        x_slider =  tk.Scale(self, from_=-100, to=100, orient=tk.HORIZONTAL, label="Target X (plane-centered Earth coordinates)",
                                variable=self.x, command=self.update_quaternion, length=300)
        y_slider =  tk.Scale(self, from_=-100, to=100, orient=tk.HORIZONTAL, label="Target Y",
                                variable=self.y, command=self.update_quaternion, length=300)
        z_slider =  tk.Scale(self, from_=-100, to=100, orient=tk.HORIZONTAL, label="Target Z",
                                variable=self.z, command=self.update_quaternion, length=300)
        x_slider.pack()
        y_slider.pack()
        z_slider.pack()

        # Label to display quaternion
        self.quaternion_label = tk.Label(self, text="Quaternion: ")
        self.quaternion_label.pack()

    def update_quaternion(self, event=None):
        # Get Euler angles from sliders
        yaw = self.yaw.get()
        pitch = self.pitch.get()
        roll = self.roll.get()
        x = self.x.get()
        y = self.y.get()
        z = self.z.get()
        attitude = attitude_from_yaw_pitch_roll(yaw, pitch, roll, degrees=True)

        

        x_b, y_b, z_b = transform_from_earth_to_body(attitude, [x, y, z])

        azimuth_earth = calculate_azimuth(x, y)*180/np.pi
        azimuth_body = calculate_azimuth(x_b, y_b)*180/np.pi
        yaw_corrected_azim = normalize_angle(azimuth_body + yaw, 180, -180)
        azimuth_error = np.abs(azimuth_earth - yaw_corrected_azim)

        forward_vector_b = [1, 0, 0]
        aircraft_vector = transform_from_body_to_earth(attitude, forward_vector_b)
        wing_vector_b = [0, 1, 0]
        wing_vector = transform_from_body_to_earth(attitude, wing_vector_b)
        down_vector_b = [0, 0, 1]
        down_vector = transform_from_body_to_earth(attitude, down_vector_b)

        import pyquaternion
        pyquat = pyquaternion.Quaternion([attitude.as_quat()[3], attitude.as_quat()[0], attitude.as_quat()[1], attitude.as_quat()[2]])
        # pyquaternion seems to be wrong. scipy and wolframalpha give the same answer, but pyquaternion dowsnt
        # https://www.wolframalpha.com/input?i=euler+angles
        
        self.quaternion_label.config(text=f"\nForward vector (earth): {aircraft_vector},\n wing vector (earth): {wing_vector}\ndown vector(earth):  {down_vector}"
                                     f"\nTarget in body coordinates: [{x_b}, {y_b}, {z_b}]"
                                     f"\nAbsolute azimuth:\t{azimuth_earth:10.2f}\t"
                                     f"\nMeasured azimuth:\t{azimuth_body:10.2f}\t"
                                     f"\nYaw-corrected abs azim:{yaw_corrected_azim:10.2f}"
                                     f"\nAZIMUTH ERROR:\t{azimuth_error:10.2f}\t"
                                     f"\n to Euler:\t{attitude.as_euler('ZYX', degrees=True)}"
                                     f"\n quaternion:\t{attitude.as_quat()}"
                                     f"\n pyquaterni:\t{pyquat}"
                                     f"\n pyquaternion to Euler (wrong):\t{[a *(180/np.pi) for a in pyquat.yaw_pitch_roll]}")

def calculate_error(yaw, pitch, roll, x, y, z):

    attitude = attitude_from_yaw_pitch_roll(yaw, pitch, roll, degrees=True)
    x_b, y_b, z_b = transform_from_earth_to_body(attitude, [x, y, z])
    azimuth_earth = calculate_azimuth(x, y)*180/np.pi
    azimuth_body = calculate_azimuth(x_b, y_b)*180/np.pi
    yaw_corrected_azim = normalize_angle(azimuth_body + yaw, 180, -180)
    azimuth_error = np.abs(azimuth_earth - yaw_corrected_azim)
    return azimuth_earth, azimuth_body, yaw_corrected_azim, azimuth_error


def attitude_from_yaw_pitch_roll(yaw, pitch, roll, degrees=False):
    # Calculate rotation from Euler angles
    r = Rotation.from_euler('ZYX', [yaw, pitch, roll], degrees=degrees)
    # r = Rotation.from_euler('xyz', [yaw, pitch, roll], degrees=degrees)
    return r

def transform_from_earth_to_body(attitude: Rotation, vector: list):
    # transforms a vector from earth coordinate frame to body coordinate frame
    return attitude.apply(vector, inverse=True)

def transform_from_body_to_earth(attitude: Rotation, vector: list):
    # transforms a vector from body coordinate frame to earth coordinate frame
    return attitude.apply(vector, inverse=False)

def calculate_azimuth(x, y):
    # return np.arctan(y/x)*180/np.pi
    return np.arctan2(y, x) #?????




if __name__ == "__main__":
    app = HeadingCalculator()
    app.mainloop()
