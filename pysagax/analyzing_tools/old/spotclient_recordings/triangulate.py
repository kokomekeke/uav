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
from pysagax import normalize_angle
import nautipy
from geographiclib.geodesic import Geodesic


folder = "C:\\Users\\p\\Documents\\measurments\\ocsa_231212\\"
file = "\\laptop1-box1\\20231212_105551_merged_trimmed_interpolated.csv"

def triangulate(lat1, lon1, azim1, lat2, lon2, azim2, lat_gt=0, lon_gt=0):
    if any(np.isnan([lat1, lon1, azim1, lat2, lon2, azim2, lat_gt, lon_gt])):
        return [float("nan")]*3
    azim1 = normalize_angle(azim1*180/np.pi, 360, 0)
    azim2 = normalize_angle(azim2*180/np.pi, 360, 0)
    p1 = nautipy.Pos(lat1, lon1)
    p2 =nautipy.Pos(lat2, lon2)
    target = nautipy.triangulate(p1, azim1, p2, azim2)

    azim1_back = nautipy.bearing(p1, target)
    azim2_back = nautipy.bearing(p2, target)
    if abs(azim1_back - azim1)>5 or abs(azim2_back - azim2)>5:
        return [float("nan")]*3 #the azimut lines dont intersect (needs to be geometrically checked)
        # nautipy.triangulate() still returns the intersection of the lines 
        #    even when the half-lines from p1 and p2 dont intersect.
        #    (actually 2 great circles always intersect 2 times. 
        #     We return nan values here, when their closest intersection should have 
        #     been measured by flipping one or both measured bearings by 180°)
        #     I think, but who knows. If you use this, check if the results are sensible for yourself

    error = nautipy.haversine(target, nautipy.Pos(lat_gt, lon_gt)) * 1000
    return target.lat, target.lon, error #measured lat, lon, error in meters

target = triangulate(47.329231836457815, 19.30931917297361, (80.281/180*np.pi), 47.33258404841499, 19.315863762969947, (137.082/180*np.pi), 47.33034738343002, 19.318932210082984)
print(target)
target = triangulate(47.329231836457815, 19.30931917297361, np.pi+(80.281/180*np.pi), 47.33258404841499, 19.315863762969947, (137.082/180*np.pi), 47.33034738343002, 19.318932210082984)
print(target)
target = triangulate(47.329231836457815, 19.30931917297361, (80.281/180*np.pi), 47.33258404841499, 19.315863762969947, np.pi+(137.082/180*np.pi), 47.33034738343002, 19.318932210082984)
print(target)
target = triangulate(47.329231836457815, 19.30931917297361, np.pi+(80.281/180*np.pi), 47.33258404841499, 19.315863762969947, np.pi+(137.082/180*np.pi), 47.33034738343002, 19.318932210082984)
print(target)
target = triangulate(47.329231836457815, 19.30931917297361,(137.082/180*np.pi) , 47.33258404841499, 19.315863762969947, (80.281/180*np.pi), 47.33034738343002, 19.318932210082984)
print(target)

#target= 52.24460908165849, 21.063955937499976 -> (52.25395557470785, 21.07609524205066)
#target= 70.06745152498283, 27.567862187499976 -> (71.26085996302612, 28.90466063630995)
#target= 47.33034738343002, 19.318932210082984 -> (47.33034736549298, 19.318932244633377)(47.33034736549298, 19.318932244633377, 724.4855005934174)
result = pd.read_csv(f"{folder}{file}")
# result = result.iloc[0:100].reset_index()

result[["lat_tx0", "lon_tx0", "error0"]] = pd.DataFrame(result.apply(lambda x: triangulate(x["lat_rx1"], x["lon_rx1"], x["df_corrected_rx1"], x["lat_rx2"], x["lon_rx2"], x["df_corrected_rx2"], x["lat_tx"], x["lon_tx"]), axis=1).tolist())
print(1)
result[["lat_tx1", "lon_tx1", "error1"]] = pd.DataFrame(result.apply(lambda x: triangulate(x["lat_rx1"], x["lon_rx1"], x["df_corrected_mean_rx1"], x["lat_rx2"], x["lon_rx2"], x["df_corrected_mean_rx2"], x["lat_tx"], x["lon_tx"]), axis=1).tolist())
print(2)

def circmedian(angs):
    pdists = angs[np.newaxis, :] - angs[:, np.newaxis]
    pdists = (pdists + np.pi) % (2 * np.pi) - np.pi
    pdists = np.abs(pdists).sum(1)
    return angs[np.argmin(pdists)]
med_fn = lambda x: circmedian(x.values)

window_size = 500
# med_fn = lambda x: circmedian(x.values)
mean_fn = lambda x: scipy.stats.circmean(x, high=np.pi, low=-np.pi, nan_policy="omit")
result["df_corrected_med500_rx1"] = result["df_corrected_rx1"].rolling(window_size).apply(med_fn).map(lambda x: normalize_angle(x))
result["df_corrected_med500_rx2"] = result["df_corrected_rx2"].rolling(window_size).apply(med_fn).map(lambda x: normalize_angle(x))
print(2.5)
result[["lat_tx500", "lon_tx500", "error500"]] = pd.DataFrame(result.apply(lambda x: triangulate(x["lat_rx1"], x["lon_rx1"], x["df_corrected_med500_rx1"], x["lat_rx2"], x["lon_rx2"], x["df_corrected_med500_rx2"], x["lat_tx"], x["lon_tx"]), axis=1).tolist())



result.to_csv(f"{folder}{file[:-4]}_triangulated_med500.csv")





