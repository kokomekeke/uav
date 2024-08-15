import csv
import pandas as pd
import click
from tqdm import tqdm
import numpy as np
from collections import defaultdict
from dateutil.parser import isoparse
from scipy.spatial.transform import Rotation
from pysagax.util.mat import normalize_angle
from geographiclib.geodesic import Geodesic

from pysagax.analyzing_tools import plot_results, protorec_to_csv
from multiprocessing import Process
import sys
from time import sleep


from datetime import datetime
import os

BOLD = "\033[1m"
RED = "\033[91m"
ENDBOLD = "\033[0m"


def bold(s: str):
    return BOLD + s + ENDBOLD


def red(s: str):
    return RED + s + ENDBOLD


global detection_count
detection_count = 0


def add_roi_id_0(path):
    """
    the .detectrec files has empty detection.roiId fields for when we detected a signal that has roi

    eg: if detection1.roiId is empty, but detection1.frequency is not, that means that detection1.roiId should be 0
    """

    df = pd.read_csv(path)
    if "detection0.frequency" not in df.keys():
        print(bold(red("The file doesn't contain any signal detections")))
        return

    # find columns like: detectionX.roiId (X is an integer)
    roi_id_cols = [k for k in df.keys() if k.endswith("roiId")]
    if len(roi_id_cols) == 0:
        idx = df.columns.get_loc("detection0.frequency")
        df.insert(idx, "detection0.roiId", np.nan)
        roi_id_cols = ["detection0.roiId"]
    detection_freq_cols = [
        ".".join(k.split(".")[:-1] + ["frequency"]) for k in roi_id_cols
    ]  # find the corresponding detectionX.frequency

    for f_key, id_key in zip(detection_freq_cols, roi_id_cols):
        df[id_key] = df.apply(
            lambda r: (
                int(0) if np.isnan(r[id_key]) and not np.isnan(r[f_key]) else r[id_key]
            ),
            axis=1,
        )  # roiId is 0 if it hasn't been set but other field(frequency) in the detection has been

    bandwidth_cols = [".".join(k.split(".")[:-1] + ["bandwidth"]) for k in roi_id_cols]
    # bandwidth calculation not yet implemented, so make sure the columns exist
    for bc, fc in zip(bandwidth_cols, detection_freq_cols):
        if bc not in df.keys():
            idx = df.columns.get_loc(fc)
            df.insert(idx + 1, bc, None)

    df.to_csv(path, index=False)


def filer_detections_by_roi_id(full_csv_path, detectrec_folder):
    # TODO: should've used pandas.
    out_data = defaultdict(list)  # defaultdict to ignore key errors

    with open(full_csv_path, mode="r") as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames

        # Extract general information columns (those that don't start with 'detection')
        general_info_headers = [
            header for header in headers if not header.startswith("detection")
        ]
        detection_info_headers = [
            header for header in headers if header.startswith("detection")
        ]

        for row in tqdm(reader, total=detection_count):
            general_info = {header: row[header] for header in general_info_headers}

            # Extract detection-related information
            detection_info = defaultdict(dict)
            for header in detection_info_headers:
                parts = header.split(".")
                detection_index = parts[0]  # e.g. detection0
                attribute = parts[1]  # subfields of detections e.g. roiId, azimuth etc.
                # subfield values:
                detection_info[detection_index][attribute] = row[header]

            # Organize data by detection.roiId
            for detection_index, attributes in detection_info.items():
                if "roiId" in attributes:
                    detection_id = attributes["roiId"]
                    if detection_id:  # Ensure the detection_id is not empty

                        combined_info = general_info | {
                            f"detection.{k}": v for k, v in attributes.items()
                        }

                        out_data[int(float(detection_id))].append(combined_info)

    # Write separate csv files for each detection ID
    filtered_detection_paths = {}
    for i, (detection_id, rows) in enumerate(out_data.items()):
        if rows:
            detection_headers = general_info_headers + [
                f"{attr}" for attr in rows[0].keys() if attr.startswith("detection.")
            ]
            # print(detection_headers)

            output_folder = os.path.join(detectrec_folder, f"roi_id_{detection_id}")
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            output_csv = os.path.join(
                output_folder, f"detection_roi_id_{detection_id}.csv"
            )
            filtered_detection_paths |= {detection_id: output_csv}
            print(f"Writing file {i+1}/{len(out_data)}: {output_csv}")

            with open(output_csv, mode="w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=detection_headers)
                writer.writeheader()
                writer.writerows(rows)
    return filtered_detection_paths


class Transmitter:
    def __init__(self, frequency, latitude, longitude) -> None:
        self.frequency = frequency
        self.latitude = latitude
        self.longitude = longitude

    def __str__(self) -> str:
        return f"Transmitter with frequency={self.frequency/1e6:.4f}MHz, latitude={self.latitude}, longitude={self.longitude}"


def calculate_error_stationary_tx(
    detection_df: pd.DataFrame, output_path, tx: Transmitter
):
    """
    Calculates the correct DF angle and applies the heading data to the measurements (only yaw!)
    """

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
        Returns the azimuth from the reciever coordinates to the tx coords and the distance between them in metres
        """

        result = Geodesic.WGS84.Inverse(lat_rx, lon_rx, lat_tx, lon_tx)

        azim = result["azi1"] * np.pi / 180
        dist = result["s12"]
        return azim, dist

    def insert_empty_rows(df, dt):
        """insert empyty rows between consecutive datapoints more than dt seconds apart
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

    if "headingData.altitude" not in detection_df.keys():
        detection_df["headingData.altitude"] = None
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
                tx.latitude,
                tx.longitude,
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
    detection_df["elapsed_time"] = detection_df["time"].apply(
        lambda x: isoparse(x).timestamp() - start_ts
    )

    detection_df = insert_empty_rows(detection_df, 10)

    detection_df.to_csv(output_path)


def run_error_calc_with_stationary_tx(paths, transmitters: list[Transmitter]):
    output_paths = {}
    calculation_arguments = []
    for i, (roi_id, input) in enumerate(paths.items()):
        # print(f"Creating output csv {i+1}/{len(paths)}: {output}")
        df = pd.read_csv(input)

        frequencies = df[df["detection.frequency"] > 0]
        detection_freq = frequencies["detection.frequency"].mean()
        print("Detection", detection_freq)
        # print("\n DETECTION FREQ", detection_freq)
        # found_transmitter = None
        for t in transmitters:
            if abs(t.frequency - detection_freq) < 30000:  # +/- 30kHz good threshold?
                print(
                    f"\tDetections with ROI ID {roi_id} seem to be of transmitter with frequency={t.frequency/1e6:.4f}MHz"
                )

                output = ".".join(input.split(".")[:-1]) + "_withError.csv"
                output_paths |= {roi_id: output}

                found_transmitter = t
                calculation_arguments.append((df, output, found_transmitter))
    if not len(calculation_arguments):
        print(
            red(
                bold(
                    "\nWARNING: no matching detections found for the given transmitter frequencies"
                )
            )
        )
        return {}
    for i, args in enumerate(calculation_arguments):
        print(
            bold(
                f"\nCALCULATIONG GEOLOCATION ERROR {i+1}/{len(calculation_arguments)}: {args[1]}"
            )
        )
        calculate_error_stationary_tx(*args)
    print("You can make plots using plot.py from these files.")
    return output_paths


def trim_detections(paths, trim_by="detection.meanAzimuth"):
    """
    This script removes lines from the input .csv file where the field
    defined by --trim-by option (default: detection.meanAzimuthCompensated) doesn't change  (compared to the previous row).

    SOURCE source .csv file
    OUTPUT is the output CSV file (not required).
    """
    trimmed_paths = {}
    for i, (roi_id, input) in enumerate(paths.items()):
        output = ".".join(input.split(".")[:-1]) + "_trimmed.csv"
        trimmed_paths |= {roi_id: output}
        print(bold(f"Creating trimmed csv {i+1}/{len(paths)}:") + f" {output}")
        df = pd.read_csv(input)

        keep_rows = df[trim_by].diff()
        keep_rows[0] = 1
        df = df[keep_rows != 0]
        df.to_csv(output)
    return trimmed_paths


def make_qgis_csv(paths):
    """Creates .csv-s that can be used by qgis"""
    qgis_paths = {}
    for i, (roi_id, input) in enumerate(paths.items()):
        output = ".".join(input.split(".")[:-1]) + "_qgis.csv"
        qgis_paths |= {roi_id: output}
        print(bold(f"Creating qgis csv {i+1}/{len(paths)}:") + f" {output}")
        df = pd.read_csv(input)
        qgis = pd.DataFrame()
        qgis["detection_id"] = np.nan  # TODO
        qgis["uav_id"] = np.nan  # TODO
        qgis["uav_event_id"] = np.nan  # TODO
        qgis["frequency"] = df["detection.frequency"]
        qgis["signal_strength"] = df["detection.strength"]
        qgis["bandwidth"] = df["detection.bandwidth"]
        qgis["snr"] = df["detection.snr"]
        qgis["lob_azim_deg"] = df["detection.meanAzimuthCompensated"] * 180 / np.pi
        qgis["lob_elev_deg"] = np.nan  # TODO: compensated elevation based on YPR
        qgis["precision"] = np.nan  # TODO
        qgis["timestamp"] = df["time"]
        qgis["uav_pos_lat"] = df["headingData.gpsLat"]
        qgis["uav_pos_lon"] = df["headingData.gpsLon"]
        qgis["uav_pos_altitude"] = df["headingData.altitude"]
        qgis["uav_pos_q0"] = df["headingData.quaternion0"]
        qgis["uav_pos_q1"] = df["headingData.quaternion1"]
        qgis["uav_pos_q2"] = df["headingData.quaternion2"]
        qgis["uav_pos_q3"] = df["headingData.quaternion3"]
        qgis["roi_identifier"] = df["detection.roiId"]

        qgis.to_csv(output)


def call_plotting(paths, plot_mode):
    if plot_mode == "off" or len(paths) == 0:
        return
    print(bold("\nPLOTTING RESULTS") + " (this might take a while)")

    def silent_plot(*args, **kwargs):
        sys.stderr = open("/dev/null", "w")
        sys.stdout = open("/dev/null", "w")  # Shouldn't suppress pandas's warnings
        plot_results.main(*args, **kwargs)

    to_run_list = [["--save-png", "--path", str(input)] for input in paths.values()]
    if plot_mode != "show":
        for to_run in to_run_list:
            to_run.append("--dont-show-plot")

    procs = []
    for i, to_run in enumerate(to_run_list):
        print(f"Creating plots {i+1}/{len(paths)}")
        p = Process(
            target=silent_plot, args=[to_run], kwargs={"standalone_mode": False}
        )
        p.start()
        procs.append(p)

    dots = ""
    while True:
        statuses = [not p.is_alive() for p in procs]
        progress = sum(statuses)
        dots = (dots + ".") if len(dots) < 4 else ""  # blinking dots for fun
        print(f"MAKING PLOTS {progress}/{len(procs)} {dots}    ", end="\r")
        if progress == len(procs):
            break
        sleep(0.3)
    print(f"MAKING PLOTS {len(procs)}/{len(procs)}")

    for i, p in enumerate(procs):
        p.join()
    print("Plotting finished")


@click.command()
@click.argument("path", type=click.Path(exists=True), required=True)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=True, file_okay=False),
    default="",
    required=False,
    help="Location of the output folder. Same as input if not specified.",
)
@click.option(
    "--transmitters",
    "-T",
    type=(float, float, float),
    multiple=True,
    help="Transmitter data in (frequency latitude longitude) tuples. \b\nExample with 2 transmitters: -TX 433.6e6 19.05485 47.68549 -TX 149.6e6 19.0521 47.7205",
)
@click.option(
    "--no-transmitters",
    is_flag=True,
    help="Prevents prompting for transmitters if none were provided.",
)
@click.option(
    "--sync-heading",
    type=click.Path(),
    required=False,
    help="Use if the recording doesn't contain usable heading data. The file location for Magellium's flightinfo.txt file to update heading data from.",
)
@click.option(
    "--plot",
    type=click.Choice(["off", "save", "show"]),
    required=False,
    default="save",
    help="Create plots from DF error calculations. save -> save .png; show -> save .jpg and show matplotlib windows.",
    prompt="Create plots?",
)
@click.option(
    "--qgis/--no-qgis",
    help="Generate .csv files for detections to create map visualizations using qgis",
    prompt="Do you want to generate .csv for QGIS map visualizations?",
    default=True,
)
def main(path, output, transmitters, no_transmitters, sync_heading, plot, qgis):
    """
    Performs the steps necessary for extracting data from .detectrec recordings. Calculates error of DF measurements for known transmitters (currently only stationary transmitters are supported) and plots the results.
    """
    # PREPARING TRANSMITTERS
    if (
        not len(transmitters)
        and not no_transmitters
        and click.confirm("\nDo you want to add transmitters?", default=True)
    ):
        transmitters = []
        i = 0
        while True:
            f = click.prompt("\tTransmitter #{i} frequency:", type=float)
            lat = click.prompt("\tTransmitter #{i} latitude:", type=float)
            lon = click.prompt("\tTransmitter #{i} longitude:", type=float)
            transmitters.append(Transmitter(f, lat, lon))
            i += 1
            if not click.confirm(
                "Do you want to add another transmitter?", default=True
            ):
                break
    else:
        transmitters = [Transmitter(t[0], t[1], t[2]) for t in transmitters]

    # PREPARING PATH VARIABLES
    if output == "":
        output = os.path.dirname(path)
    output_folder = os.path.join(output, os.path.splitext(os.path.basename(path))[0])
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    full_csv_path = os.path.join(output_folder, "full.csv")

    print(
        bold(f"\nRUNNING WITH THE FOLLOWING PARAMETERS:")
        + f"\n\t{BOLD}SOURCE PATH:{ENDBOLD} {path}"
        f"\n\t{BOLD}RESULT DIR:{ENDBOLD} {output_folder}"
        f"\n\t{BOLD}FULL DETECTION CSV:{ENDBOLD} {full_csv_path}"
        + f"\n\t{BOLD}TRANSMITTERS:{ENDBOLD}\n"
        + "".join(
            [f"\t\t{BOLD}#{i}{ENDBOLD} {t}\n" for i, t in enumerate(transmitters)]
        )
        + f"\t{BOLD}SYNCING HEADING: {'from ' + sync_heading if sync_heading else 'disabled'}"
        f"\n\t{BOLD}GENERATE .CSV FOR QGIS: {ENDBOLD}: {qgis}"
        f"\n\t{BOLD}PLOT MODE: {ENDBOLD}: {plot}"
    )

    print(bold(f"\nCONVERTING TO .CSV"))
    # convert_detectrec_to_csv(path, full_csv_path, ignore_type=["Telemetry"]) #TODO: use pandas in this step
    global detection_count
    detection_count = protorec_to_csv.main(
        ["--skip-type", "Telemetry", path, full_csv_path], standalone_mode=False
    )

    print(bold(f"\nCORRECTING") + " where empty roiID should be 0")
    add_roi_id_0(full_csv_path)

    if sync_heading:
        print(bold(f"\nSYNCING HEADING DATA FROM EXTERNAL SOURCE"))
        print("Not yet implemented, just say no next time")
    else:
        print(bold(f"\nSKIPPING SYNCING HEADING"))

    print(bold(f"\nSEPARATING DETECTIONS BY RoiId"))
    filtered_detection_paths = filer_detections_by_roi_id(full_csv_path, output_folder)

    print(bold(f"\nMATCHING TX FREQUENCY TO DETECTIONS"))
    detection_error_paths = run_error_calc_with_stationary_tx(
        filtered_detection_paths, transmitters
    )

    print("\n")
    trimmed_detection_paths = trim_detections(detection_error_paths)

    if qgis:
        print()
        make_qgis_csv(trimmed_detection_paths)

    call_plotting(detection_error_paths, plot)


if __name__ == "__main__":
    main()
