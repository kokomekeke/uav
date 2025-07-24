import click
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import math
pd.options.mode.copy_on_write=True
"""
Useful tool for rotated measurements to see if the azimuth changes linearly.
for plotting .csv files made from .detectrec files using protorec_to_csv.py

#TODO: better names for protorec and detectrec and the 2 csv parsers. Their results should also be compatible.
"""

save_png_g = False


def plot(
    savepath,
    title,
    x_values,
    peaks,  # pandas DataFrame containing columns ["peaks0", "peaks1", etc]
    angles,
    deviations,
):

    fig, ax = plt.subplots(figsize=(19.20, 10.80))
    ax.grid(visible=True)

    angle_ax = ax.twinx()
    angle_ax.set_ylabel("mean azimuth angle")
    angle_ax.set_ylim(-181, 181)
    angle_ax.set_yticks([a for a in range(-180, 181, 30)])

    # peaks["maxpeak"] = peaks[["peak0", "peak1", "peak2", "peak3"]].max(axis=1)
    # peaks["minpeak"] = peaks[["peak0", "peak1", "peak2", "peak3"]].min(axis=1)
    peaks["maxpeak"] = peaks.max(axis=1)
    peaks["minpeak"] = peaks.min(axis=1)
    peaks["maxpeak2"] = peaks["maxpeak"].rolling(1, center=True).max()
    peaks["minpeak2"] = peaks["minpeak"].rolling(1, center=True).min()
    adc_resolution = 2**15 - 1
    peaks["maxpeak2"] = peaks["maxpeak2"].map(
        lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
    )
    peaks["minpeak2"] = peaks["minpeak2"].map(
        lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
    )
    peaks["minpeak2"] = peaks["minpeak2"].map(
        lambda x: -1 if x > -1 else x
    )  # make the peak band visible if all channels have full scale peak values
    min_dbfs_level = 20 * math.log10(1 / adc_resolution)

    # Hacky way to show everything on one legend. (since ax.legend() looks better than fig.legend())
    ax.plot([], [], label="mean azimuth", color="black")
    ax.fill_between(
        x=[],
        y1=[],
        y2=[],
        color="red",
        alpha=0.15,
        linewidth=0,
        label="DF angle deviation",
    )

    angle_ax.plot(
        x_values,
        angles * 180 / np.pi,
        color="black",
        label="Azimuth",
        zorder=10,
        linewidth=4,
    )
    dev_top = (
        (angles + deviations) * 180 / np.pi
    )  # .map(lambda x: pysagax.normalize_angle(x)*180/np.pi)
    dev_bot = (angles - deviations) * 180 / np.pi
    angle_ax.fill_between(
        x=x_values,
        y1=dev_top,
        y2=dev_bot,
        color="red",
        alpha=0.15,
        linestyle="None",
        linewidth=0,
        label="DF angle deviation",
    )

    print("\rPlotting:\t|-|" , end="")
    ax.plot(
        x_values,
        peaks["peaks0"].map(
            lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
        ),
        color="gold",
        label="ch0",
        zorder=1,
        alpha=0.6,
    )
    ax.plot(
        x_values,
        peaks["peaks1"].map(
            lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
        ),
        color="blue",
        label="ch1",
        zorder=10,
        alpha=0.6,
    )
    ax.plot(
        x_values,
        peaks["peaks2"].map(
            lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
        ),
        color="green",
        label="ch2",
        zorder=1,
        alpha=0.6,
    )
    ax.plot(
        x_values,
        peaks["peaks3"].map(
            lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
        ),
        color="red",
        label="ch3",
        zorder=10,
        alpha=0.6,
    )
    print("\rPlotting:\t|█|")

    ax.fill_between(
        x=x_values,
        y1=peaks["maxpeak2"],
        y2=peaks["minpeak2"],
        color="black",
        alpha=0.15,
        linestyle="None",
        linewidth=0,
        label="range of peak dBFS for ch0..ch3",
    )
    ax.set_ylim(min_dbfs_level, 0)

    ax.set_ylabel("peak dBFS")
    ax.set_xlabel("Time (s)")

    ax.legend(ncols=7, fancybox=True, shadow=True, loc=(0.01, 1.01))
    fig.suptitle(title)
    fig.set_constrained_layout(constrained=True)

    global save_png_g
    if save_png_g:

        print("\rSaving:\t\t|-|   ", end="")
        fig.savefig(
            savepath,
            dpi=500,
        )
        print("\rSaving:\t\t|█|")


@click.command()
@click.option(
    "-p",
    "--path",
    type=str,
    required=True,
    help="Location for the .csv file",
)
@click.option(
    "--save-png",
    type=bool,
    required=False,
    is_flag=True,
    show_default=False,
    default=False,
    help="auto save .png images of the generated plots",
)
@click.option(
    "--dont-plot",
    type=bool,
    required=False,
    is_flag=True,
    show_default=False,
    default=False,
    help="dont show plot windows. Use it with --save-png",
)
def main(
    path: str,
    save_png: bool = False,
    dont_plot:bool = False,
):

    global save_png_g
    save_png_g = save_png
    print(f"\nRunning on file {path}")

    print("\rReading:\t|-|", end="")
    detection_df = pd.read_csv(path)
    print("\rReading:\t|█|")

    print("\rProcessing:\t|-|", end="")
    detection_df["elapsed_time"] = (
        detection_df["record_time"] - detection_df["record_time"][0]
    )
    x_values = detection_df["elapsed_time"]
    print("\rProcessing\t|█|")

    plot(
        savepath=".".join(path.split(".")[:-1]) + "_peaks.png",
        title=f"{int(detection_df['detection0.frequency'].round(-5).mode()/1e5)/10} MHz, channel peaks",
        x_values=x_values,
        peaks=detection_df[["peaks0", "peaks1", "peaks2", "peaks3"]],
        angles=detection_df["detection0.meanAzimuth"],
        deviations=detection_df["detection0.deviation"],
    )
    if not dont_plot:
        print("Opening plot window", end="\r")
        plt.show(block=True)
    print("Finished             ")

if __name__ == "__main__":
    main()
