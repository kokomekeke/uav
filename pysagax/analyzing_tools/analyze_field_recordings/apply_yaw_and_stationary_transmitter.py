import click
import pandas as pd
import numpy as np
from scipy.spatial.transform import Rotation
from pysagax.util.mat import normalize_angle
from tqdm import tqdm
from dateutil.parser import isoparse

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

def azim_and_dist_from_points(lat_tx, lon_tx, lat_rx, lon_rx):
    """
    copied from merge_stationary_transmitter.py
    Returns the azimuth from the reciever coordinates to the tx coords and the distance between them in metres
    """
    ##calculate gt azimuth and distance from transmitter and reciever coordinates

    import scipy
    from geographiclib.geodesic import Geodesic

    # print(lat_tx, lon_tx, lat_rx, lon_rx)
    # print(type(lat_tx), type(lon_tx), type(lat_rx), type(lon_rx))
    result = Geodesic.WGS84.Inverse(lat_rx, lon_rx, lat_tx, lon_tx)
    # print(result)
    azim = result["azi1"] * np.pi / 180
    dist = result["s12"]
    return azim, dist


def insert_empty_rows(df, dt):
    """ insert empyty rows between consecutive datapoints more than dt seconds apart
        so that they aren't connected on the final plots
    """
    columns = df.columns
    new_rows = []
    for i in tqdm(range(len(df) - 1)):
        new_rows.append(df.iloc[i])
        time_diff = (
            isoparse(df["time"].iloc[i + 1]).timestamp()
            - isoparse(df["time"].iloc[i]).timestamp()
        )
        # time_diff = df['seconds'].iloc[i + 1] - df['seconds'].iloc[i]
        if time_diff > dt:
            empty_row = pd.Series({col: np.nan for col in columns})
            new_rows.append(empty_row)
    new_rows.append(df.iloc[-1])
    new_df = pd.DataFrame(new_rows, columns=columns)
    return new_df


@click.command()
@click.option(
    "-p",
    "--path",
    type=str,
    required=True,
    help="Location for the .csv file",
)
@click.option(
    "--lat",
    default=43.351817,
    type=float,
    required=False,
    help="Stationary transmitter lattitude",
)
@click.option(
    "--lon",
    default=1.220034,
    type=float,
    required=False,
    help="Stationary transmitter lattitude",
)
def main(path: str, lat: float, lon: float):
    """
    Calculates the correct DF angle and applies the heading data to the measurements (only yaw!)
    Default TX lat lon: Longages, France
    """
    detection_df = pd.read_csv(path)

    # calculate yaw
    detection_df[["headingData.yaw", "headingData.pitch", "headingData.roll"]] = (
        detection_df.apply(
            lambda r: ypr(
                r["headingData.quaternion0"],
                r["headingData.quaternion1"],
                r["headingData.quaternion2"],
                r["headingData.quaternion3"],
            ),
            axis=1,
            result_type="expand",
        )
    )
    # calculate yaw-Compensated df angles
    detection_df["detection.azimuthCompensated"] = (
        detection_df["detection.azimuth"] + detection_df["headingData.yaw"]
    ).map(lambda x: normalize_angle(x))
    detection_df["detection.meanAzimuthCompensated"] = (
        detection_df["detection.meanAzimuth"] + detection_df["headingData.yaw"]
    ).map(lambda x: normalize_angle(x))

    # detection_df["detection.meanAzimuth"]

    detection_df[["detection.gtAzimuthCompensated", "detection.TxRxDistance"]] = (
        detection_df.apply(
            lambda r: azim_and_dist_from_points(
                lat,
                lon,
                r["headingData.gpsLat"],
                r["headingData.gpsLon"],
            ),
            axis=1,
            result_type="expand",
        )
    )
    # calculate correct azimuth without heading compensation
    detection_df["detection.gtAzimuth"] = (
        detection_df["detection.gtAzimuthCompensated"] - detection_df["headingData.yaw"]
    ).map(lambda x: normalize_angle(x))


    detection_df["detection.azimuthError"] = (
        detection_df["detection.gtAzimuthCompensated"]
        - detection_df["detection.azimuthCompensated"]
    ).map(lambda x: normalize_angle(x))
    detection_df["detection.meanAzimuthError"] = (
        detection_df["detection.gtAzimuthCompensated"]
        - detection_df["detection.meanAzimuthCompensated"]
    ).map(lambda x: normalize_angle(x))


    start_ts = isoparse(detection_df["time"][0]).timestamp()
    detection_df["elapsed_time"] = detection_df["time"].apply(lambda x: isoparse(x).timestamp() - start_ts) 

    detection_df = insert_empty_rows(detection_df, 10)

    detection_df.to_csv(".".join(path.split(".")[:-1]) + "yaw-Compensated.csv")


if __name__ == "__main__":
    main()
