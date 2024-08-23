"""
For viewing protobuf spectrogram recordings (.protorec files)
In progresss
Usage: run with the --help flag
"""

from pysagax.message.proto_stream_to_file import FileStreamer
import pysagax.message.data_pb2 as proto_data
from pysagax.util.protobuf_spectrum_utils import protobuf_spectrum_to_numpy
from time import time
import click
import numpy as np
import matplotlib
from matplotlib import pyplot as plt


def plot_spectrogram(
    meta,
    spectrogram,
    timestamps,
    radians=False,
    ax_to_share=None,
    threshold=None,
    anti_aliasing=False,
):
    s_type = proto_data.Spectrum.SpectrumType.Name(meta["type"])
    center_freq = meta["center_frequency"]
    span = meta["span"]
    channel = meta["channel"]

    # TODO: show if there are gaps in the spectrogram recording:
    #   - insert rows of nans in spectrogram if no data for long time
    #   - or break time axis where there is a long gap

    f_min = center_freq - span / 2
    f_max = center_freq + span / 2

    if threshold is not None:
        spectrogram[spectrogram < threshold] = np.nan

    t_min = 0
    t_max = timestamps[-1] - timestamps[0]

    if meta["type"] == proto_data.Spectrum.SpectrumType.MAGNITUDE:
        db_min = -120
        db_max = 0
        cmap = matplotlib.colormaps.get_cmap("gnuplot")
        spectrogram = spectrogram * 1
    else:  # for azimuth and elevation spectrums
        if radians:
            db_max = np.pi
            db_min = -np.pi
        else:
            db_max = 180
            db_min = -180
            spectrogram = spectrogram * 180 / np.pi

        cmap = matplotlib.colormaps.get_cmap("hsv")
        # cmap = matplotlib.colormaps.get_cmap("twilight")

    fig, ax = plt.subplots()
    fig.suptitle(
        f"{s_type}: cf = {center_freq:.2e}Hz; span = {span:.2e}Hz; channel_id = {channel}"
    )

    if anti_aliasing:
        if threshold is None:
            show = ax.imshow
        else:
            show = ax.matshow
            print("WARNING: can't use anti-aliasing with threshold set.")
    else:
        show = ax.matshow

    image = show(
        spectrogram,
        cmap=cmap,  # type: ignore
        animated=True,
        vmax=db_max,
        vmin=db_min,
        aspect="auto",
        extent=[f_min, f_max, t_min, t_max],
    )
    plt.colorbar(image)
    if ax_to_share is not None:
        ax_to_share.sharey(ax)
        ax_to_share.sharex(ax)

    # TODO: make flag for enabling threshold slider
    # plt.subplots_adjust(bottom=0.25)
    # from matplotlib.widgets import Slider
    # ax_slider = plt.axes([0.1, 0.1, 0.8, 0.03])
    # slider = Slider(ax_slider, 'Threshold', -100, 0, valinit=-79,)# orientation="vertical")
    # slider.on_changed(lambda val:update(val, spectrogram, slider, image, fig))
    ax.format_coord = lambda x, y: format_coord(x, y, timestamps=timestamps)
    return ax


def update(val, spectrogram, slider, im, fig):
    """update plot if threshold slider is moved"""
    threshold = slider.val
    masked_data = np.where(spectrogram > threshold, spectrogram, np.nan)
    im.set_data(masked_data)
    fig.canvas.draw_idle()


def format_coord(x, y, timestamps):
    """Custom formatting:
    x: triple grouped digits rounded to Hz
    y: secoonds elapsed from start AND timestamp of recorded packet
    """
    from datetime import datetime

    # TODO: make timestamp display more efficient
    try:
        t_span = timestamps[-1] - timestamps[0]
        index = int(y / t_span * len(timestamps))
        ts = datetime.fromtimestamp(timestamps[index])
        ts = str(ts)[:-4]  # truncate fractional seconds to 2 decimals
    except:
        ts = ""
    return f'x={f"{x:,.0f}".replace(",", " ")} Hz; y={y:.2f} s [{ts}]'


@click.command()
@click.option(
    "-p",
    "--path",
    type=str,
    required=True,
    help="Location for the .protorec file that is to be displayed",
)
@click.option(
    "-t",
    "--threshold",
    type=float,
    default=None,
    required=False,
    help="Replace values smaller than this with NaNs in magnitude spectrum ",
)
@click.option(
    "--radians",
    "-r",
    is_flag=True,
    show_default=True,
    default=False,
    help="Plot azimuth and elevation spectrograms using radian values",
)
@click.option(
    "--aa/--no-aa",
    "anti_aliasing",
    show_default=True,
    default=False,
    help="Anti-aliasing for spectrograms. Makes certain features more visible while others less visible on the plots. Using AA is usually a little better for magnitude graphs but no AA is a lot better for angle graphs.",
)
def main(path: str, radians: bool, threshold=None, anti_aliasing=False):
    file_streamer = FileStreamer(path, mode="playback")
    start = time()
    time_list, packet_list = file_streamer.read_all()

    spectrogram_meta_list = []
    spectrogram_list = []
    timestamp_lists = []

    start = time()
    for packet, ts in zip(packet_list, time_list):
        # separate packet list into spectrograms of different channels, types (magnitude or angle), and spans and bandwidths
        if not isinstance(packet, proto_data.Measurement):
            continue
        for spectrum in packet.data:
            meta = {
                "type": spectrum.spectrum_type,
                "center_frequency": spectrum.center_frequency,
                "span": spectrum.bandwidth,
                "channel": spectrum.channel_id,
                "spectrum_bytes": len(spectrum.data),
            }
            try:
                index = spectrogram_meta_list.index(meta)
            except ValueError:
                spectrogram_meta_list.append(meta)
                index = len(spectrogram_meta_list) - 1
                spectrogram_list.append([])
                timestamp_lists.append([])

            spectrum_np = protobuf_spectrum_to_numpy(spectrum)
            spectrogram_list[index].append(spectrum_np)
            timestamp_lists[index].append(ts)

    print(len(spectrogram_list), "spectrograms found")
    if threshold:
        print(f"Plotting magnitude spectrums with a threshold of {threshold}")
    print(f"Anti aliasing turned {'ON' if anti_aliasing else 'OFF'}")

    # Lists of pyplot axes of spectrograms that cover the same part of the RF spectrum
    #   for sharing their X and Y axis so that they pan and zoom together
    ax_dict = {}

    # for meta, spectrogram, timestamps in zip(spectrogram_meta_list, spectrogram_list, timestamp_lists):
    for meta, spectrogram, timestamps in zip(
        reversed(spectrogram_meta_list),
        reversed(spectrogram_list),
        reversed(timestamp_lists),
    ):
        # For some metaphysical reason the plots have to be made in reversed order or the threshold slider doesn't work properly
        spectrogram_np = np.array(spectrogram[::-1])

        ax_key = (meta["center_frequency"], meta["span"])
        if ax_key in ax_dict:
            ax_to_share = ax_dict[ax_key][-1]
        else:
            ax_to_share = None
            ax_dict[ax_key] = []

        # only use threshold for magnitude spectrums
        # TODO: replace values with NaNs in angle spectrums where the corresponding magnitude spectrum is below the threshold
        th = (
            threshold
            if meta["type"] == proto_data.Spectrum.SpectrumType.MAGNITUDE
            else None
        )
        ax = plot_spectrogram(
            meta,
            spectrogram_np,
            timestamps,
            radians,
            ax_to_share,
            threshold=th,
            anti_aliasing=anti_aliasing,
        )

        ax_dict[ax_key].append(ax)

    plt.show(block=True)


if __name__ == "__main__":
    main()
