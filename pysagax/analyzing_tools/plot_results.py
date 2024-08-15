import click
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import math

# global save_png_g
save_png_g = False


def create_angle_plot(xlabel, ylabel, angle_angle=False):
    plot_degree_tick_location = np.arange(-180, 181, 30)
    plot_degree_tick_str = [f"{i}°" for i in np.arange(-180, 181, 30)]

    fig, ax = plt.subplots(figsize=(19.20, 10.80))
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


def plot_mean(
    savepath,
    title,
    x_values,
    df_values,
    df_values_label,
    df_error,
    df_error_label,
    correct_values,
    correct_values_label,
):
    fig, ax = create_angle_plot(xlabel="Time (s)", ylabel="Angle (deg)")
    ax.plot(x_values, df_error, color="blue", label=df_error_label)
    ax.plot(
        x_values,
        correct_values,
        color="green",
        label=correct_values_label,
        zorder=10,
        linewidth=4,
    )
    ax.plot(x_values, df_values, color="red", label=df_values_label)
    # detection_df.to_csv(".".join(path.split(".")[:-1]) + "yaw-Compensated.csv")

    ax.legend(ncols=5, fancybox=True, shadow=True, loc=(0.01, 1.01))
    fig.suptitle(title)
    fig.set_constrained_layout(constrained=True)

    global save_png_g
    if save_png_g:
        fig.savefig(
            savepath,
            dpi=500,
        )


def plot_individual(
    savepath,
    title,
    x_values,
    df_values,
    df_values_label,
    df_mean,
    df_mean_label,
    correct_values,
    correct_values_label,
):
    fig, ax = plt.subplots(figsize=(19.20, 10.80))
    ax.plot(x_values, df_values, "bo", markersize=3, label=df_values_label)
    ax.plot(
        x_values,
        correct_values,
        color="green",
        label=correct_values_label,
        zorder=10,
        linewidth=4,
    )
    ax.plot(x_values, df_mean, "r", label=df_mean_label)
    ax.set_yticks(np.arange(-180, 181, 30), [f"{i}°" for i in np.arange(-180, 181, 30)])
    ax.grid(visible=True)
    ax.set_ylabel("Angle (deg)")
    ax.set_xlabel("Time (s)")
    ax.set_ylim(-180, 180)

    ax.legend(ncols=5, fancybox=True, shadow=True, loc=(0.01, 1.01))
    fig.suptitle(title)
    fig.set_constrained_layout(constrained=True)

    global save_png_g
    if save_png_g:
        fig.savefig(
            savepath,
            dpi=500,
        )


def plot_peaks(
    savepath,
    title,
    x_values,
    peaks,  # pandas DataFrame containing columns ["peaks0", "peaks1", etc]
):

    fig, ax = plt.subplots(figsize=(19.20, 10.80))
    ax.grid(visible=True)

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

    ax.plot(
        x_values,
        peaks["peaks0"].map(
            lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
        ),
        color="gold",
        label="ch0",
        zorder=1,
        alpha=0.5,
    )
    ax.plot(
        x_values,
        peaks["peaks1"].map(
            lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
        ),
        color="blue",
        label="ch1",
        zorder=10,
        alpha=0.5,
    )
    ax.plot(
        x_values,
        peaks["peaks2"].map(
            lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
        ),
        color="green",
        label="ch2",
        zorder=1,
        alpha=0.5,
    )
    ax.plot(
        x_values,
        peaks["peaks3"].map(
            lambda x: 20 * math.log10(x / adc_resolution) if x > 0 else -1000
        ),
        color="red",
        label="ch3",
        zorder=10,
        alpha=0.5,
    )

    ax.fill_between(
        x=x_values,
        y1=peaks["maxpeak2"],
        y2=peaks["minpeak2"],
        color="black",
        alpha=0.2,
        linestyle="None",
        linewidth=0,
        label="range of peak dBFS for ch0..ch3",
    )
    ax.set_ylim(min_dbfs_level, 0)

    ax.set_ylabel("peak dBFS")
    ax.set_xlabel("Time (s)")

    ax.legend(ncols=5, fancybox=True, shadow=True, loc=(0.01, 1.01))
    fig.suptitle(title)
    fig.set_constrained_layout(constrained=True)

    global save_png_g
    if save_png_g:
        fig.savefig(
            savepath,
            dpi=500,
        )


def plot_heading(
    savepath,
    title,
    x_values,
    yaw,
    pitch,
    roll,
    dist,
):

    fig, ax = create_angle_plot(xlabel="Time (s)", ylabel="Angle (deg)")

    ax.plot(x_values, yaw, label="yaw")  # color = ???
    ax.plot(x_values, pitch, label="pitch")
    ax.plot(x_values, roll, label="roll")

    dist_ax = ax.twinx()
    dist_ax.set_ylabel("distance (m)")
    dist_ax.plot(x_values, dist, label="distance", color="black")

    # Hacky way to show everything on one legend. (since ax.legend() looks better than fig.legend())
    ax.plot([], [], label="distance", color="black")
    ax.legend(ncols=5, fancybox=True, shadow=True, loc=(0.01, 1.01))
    fig.suptitle(title)
    fig.set_constrained_layout(constrained=True)

    global save_png_g
    if save_png_g:
        fig.savefig(
            savepath,
            dpi=500,
        )


def plot_snr_and_strength(
    savepath,
    title,
    x_values,
    snr,
    strength,
):

    fig, ax = plt.subplots(figsize=(19.20, 10.80))
    ax.grid(visible=True)

    ax.set_ylabel("SNR (dB)")
    ax.set_xlabel("Time (s)")
    strength_ax = ax.twinx()
    strength_ax.set_ylabel("signal strength (dBFS)")

    ax.set_ylim(0, snr.max())
    strength_ax.set_ylim(strength.min(), 0)

    ax.plot(x_values, snr, label="SNR", color="black")
    strength_ax.plot(x_values, strength, label="strength", color="red")

    # Hacky way to show everything on one legend. (since ax.legend() looks better than fig.legend())
    ax.plot([], [], label="strength", color="red")
    ax.legend(ncols=5, fancybox=True, shadow=True, loc=(0.01, 1.01))
    fig.suptitle(title)
    fig.set_constrained_layout(constrained=True)

    global save_png_g
    if save_png_g:
        fig.savefig(
            savepath,
            dpi=500,
        )


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
    "--dont-show-plot",
    type=bool,
    required=False,
    is_flag=True,
    show_default=True,
    default=False,
    help="Will not show the plots after it ran. Use it with the --save-png flag!",
)
def main(path: str, save_png: bool = False, dont_show_plot: bool = False):
    """
    This plots!
    TODO
    """
    global save_png_g
    save_png_g = save_png

    detection_df = pd.read_csv(path)
    # TODO: check headers (detectionX.frequency or detection.frequency or qgis-compatible geojson format)
    # TODO maybe move insert empty rows here? (from apply_yaw_stationary_transmitter.py)

    # TODO: BIND X axes of graphs together for zooming

    # x_values = dataframe.index.to_list()
    x_values = detection_df["elapsed_time"]

    # # PLOT MEAN COMPENSATED DF VALUES
    plot_mean(
        savepath=".".join(path.split(".")[:-1]) + "_compensated_mean.png",
        title=f"{int(detection_df['detection.frequency'].mean()/1e5)/10} MHz, compensated mean DF values",
        x_values=x_values,
        df_values=detection_df["detection.meanAzimuthCompensated"] * 180 / np.pi,
        df_values_label=f"meanAzimuthCompensated",
        df_error=detection_df["detection.meanAzimuthError"] * 180 / np.pi,
        df_error_label=f"meanAzimuthError",
        correct_values=detection_df["detection.gtAzimuthCompensated"] * 180 / np.pi,
        correct_values_label="gtAzimuthCompensated",
    )

    # PLOT INDIVIDUAL COMPENSATED MEASUREMENTS
    plot_individual(
        savepath=".".join(path.split(".")[:-1]) + "_compensated_individual.png",
        title=f"{int(detection_df['detection.frequency'].mean()/1e5)/10} MHz, compensated individual DF values",
        x_values=x_values,
        df_values=detection_df["detection.azimuthCompensated"] * 180 / np.pi,
        df_values_label="azimuthCompensated",
        df_mean=detection_df["detection.meanAzimuthCompensated"] * 180 / np.pi,
        df_mean_label="meanAzimuthCompensated",
        correct_values=detection_df["detection.gtAzimuthCompensated"] * 180 / np.pi,
        correct_values_label="gtAzimuthCompensated",
    )

    # PLOT MEAN UNCOMPENSATED DF VALUES
    plot_mean(
        savepath=".".join(path.split(".")[:-1]) + "_uncompensated_mean.png",
        title=f"{int(detection_df['detection.frequency'].mean()/1e5)/10} MHz, uncompensated mean DF values",
        x_values=x_values,
        df_values=detection_df["detection.meanAzimuth"] * 180 / np.pi,
        df_values_label=f"meanAzimuth",
        df_error=detection_df["detection.meanAzimuthError"] * 180 / np.pi,
        df_error_label=f"meanAzimuthError",
        correct_values=detection_df["detection.gtAzimuth"] * 180 / np.pi,
        correct_values_label="gtAzimuth",
    )

    # PLOT INDIVIDUAL UNCOMPENSATED MEASUREMENTS
    plot_individual(
        savepath=".".join(path.split(".")[:-1]) + "_uncompensated_individual.png",
        title=f"{int(detection_df['detection.frequency'].mean()/1e5)/10} MHz, uncompensated individual DF values",
        x_values=x_values,
        df_values=detection_df["detection.azimuth"] * 180 / np.pi,
        df_values_label="azimuth",
        df_mean=detection_df["detection.meanAzimuth"] * 180 / np.pi,
        df_mean_label="meanAzimuth",
        correct_values=detection_df["detection.gtAzimuth"] * 180 / np.pi,
        correct_values_label="gtAzimuth",
    )
    # PLOT PEAKS
    plot_peaks(
        savepath=".".join(path.split(".")[:-1]) + "_peaks.png",
        title=f"{int(detection_df['detection.frequency'].mean()/1e5)/10} MHz, channel peaks",
        x_values=x_values,
        peaks=detection_df[["peaks0", "peaks1", "peaks2", "peaks3"]],
    )

    # PLOT SNR AND SIGNAL STRENGTH
    plot_snr_and_strength(
        savepath=".".join(path.split(".")[:-1]) + "_snr_strength.png",
        title=f"{int(detection_df['detection.frequency'].mean()/1e5)/10} MHz, SNR and signal strength",
        x_values=x_values,
        snr=detection_df["detection.snr"],
        strength=detection_df["detection.strength"],
    )

    # PLOT HEADING
    plot_heading(
        savepath=".".join(path.split(".")[:-1]) + "_heading.png",
        title=f"{int(detection_df['detection.frequency'].mean()/1e5)/10} MHz, heading",
        x_values=x_values,
        yaw=detection_df["headingData.yaw"] * 180 / np.pi,
        pitch=detection_df["headingData.pitch"] * 180 / np.pi,
        roll=detection_df["headingData.roll"] * 180 / np.pi,
        dist=detection_df["detection.TxRxDistance"],
    )

    if not dont_show_plot:
        plt.show(block=True)


if __name__ == "__main__":
    main()
