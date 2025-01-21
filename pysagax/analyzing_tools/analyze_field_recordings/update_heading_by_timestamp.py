import pandas as pd
from tqdm import tqdm
import click

from dateutil.parser import isoparse


@click.command()
@click.option(
    "-i",
    "--detection-src-file",
    type=str,
    required=True,
    help="Location for the detection .csv file",
    default = "/media/rp/data/recordings/240717 Toulouse/detectrec/20240717_151148/spotrecording_roiId.csv"
)
@click.option(
    "-h",
    "--heading-src-file",
    type=str,
    required=True,
    help="Location for the heading .csv file",
    default = "/media/rp/data/recordings/240717 Toulouse/FM_DATA_METADATA/flightinfo_merged_readable_correctquat.csv"
)
@click.option(
    "-o",
    "--detection-target-file",
    type=str,
    required=True,
    help="Location to save the updated heading file",
    default = "/media/rp/data/recordings/240717 Toulouse/detectrec/20240717_151148/spotrecording_roiId_heading_progress_bar.csv"
)
def main(detection_src_file, detection_target_file, heading_src_file):
    """Gets heading data from the csv made from Magellium's logs and merges it with our detections based on timestamps"""


    heading_df = pd.read_csv(heading_src_file)
    detections_df = pd.read_csv(detection_src_file)

    # columns_to_fill in the detection table will be added or updated by columns_to_copy of the heading table
    columns_to_fill = [
        "headingData.gpsLat", 
        "headingData.gpsLon",
        "headingData.altitude",
        "headingData.quaternion0",
        "headingData.quaternion1", 
        "headingData.quaternion2", 
        "headingData.quaternion3", 
        "headingData.timestamp",
    ]
    columns_to_copy = [
        "lat",
        "lon", 
        "altitude", 
        "q0", 
        "q1", 
        "q2", 
        "q3", 
        "time_readable"
    ]

    detections_df.insert(loc=len(detections_df.columns), column="time_diff", value=float("nan"))
    
    for i in tqdm(range(len(detections_df)), desc="Progress"):
        target_time = isoparse(detections_df["time"][i]).timestamp()
        source_index = heading_df.iloc[(heading_df['heading_time']/1e6 - target_time).abs().argsort()[:1]].index.to_list()[0]

        time_diff = (heading_df.loc[source_index, "heading_time"]/1e6 - target_time)

        if abs(detections_df.loc[i, "time_diff"]) < abs(time_diff): #better fitting data already found
            continue
    # detections_df.loc[i, columns_to_fill] = heading_df.loc[source_index, columns_to_copy]
    # detections_df.loc[i, [columns_to_fill]] = heading_df.loc[source_index, [columns_to_copy]]
        for fill, copy in zip(columns_to_fill, columns_to_copy):
            detections_df.loc[i, fill] = heading_df.loc[source_index, copy]
        detections_df.loc[i, "time_diff"] = time_diff
    # detections_df.interpolate(inplace=True)

    detections_df.to_csv(detection_target_file)

if __name__ == "__main__":
    main()
