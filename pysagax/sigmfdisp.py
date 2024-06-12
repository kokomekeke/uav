#!/usr/bin/env python3
# This tool is for displaying raw IQ files (as recorded with the early version of CoreService on Linux)

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import argparse
from argparse import ArgumentParser
import os
from os import listdir
from os.path import isfile, join
import struct

# from scipy import signal as sg
from sigmf import SigMFFile, sigmffile, SigMFCollection
from typing import Optional

max_points = 1000
datas = []
lines = []
lined = {}
fig = None
is_magnitude = False


def downsample(y, decim):
    global is_magnitude
    if decim <= 1:
        if is_magnitude:
            return 1, np.log10(np.abs(y))
        else:
            return 1, y
    new_len = y.shape[0] // decim
    z = np.zeros(new_len)
    stat_len = decim * 2
    # print(f"Downsample new len {new_len} stat_len {stat_len}")
    for i in range(0, new_len - 1, 2):
        i_start = i * decim
        i_end = min(i_start + stat_len - 1, y.shape[0])
        stat_range = y[i_start:i_end]
        if is_magnitude:
            z[i] = 20 * np.log10(np.abs(np.max(stat_range)))
            z[i + 1] = z[i]
        else:
            z[i] = np.min(stat_range)
            z[i + 1] = np.max(stat_range)
    return decim, z


def ax_update(event_ax):
    new_lim = (
        int(max(0, event_ax.get_xlim()[0])),
        int(min(len(datas[0]), event_ax.get_xlim()[1])),
    )
    decimate = (new_lim[1] - new_lim[0]) // max_points
    if decimate < 1:
        decimate = 1
    # print(f"{new_lim} -- {decimate}")
    for line, data in zip(lines, datas):
        # datas_decim = data[new_lim[0] : new_lim[1] : decimate]
        decimate, datas_decim = downsample(data[new_lim[0] : new_lim[1]], decimate)
        line.set_data(
            np.arange(new_lim[0], new_lim[0] + datas_decim.size * decimate, decimate),
            datas_decim,
        )


def on_pick(event):
    global lined
    global fig
    # On the pick event, find the original line corresponding to the legend
    # proxy line, and toggle its visibility.
    legline = event.artist
    origline = lined[legline]
    visible = not origline.get_visible()
    origline.set_visible(visible)
    # Change the alpha on the line in the legend, so we can see what lines
    # have been toggled.
    legline.set_alpha(1.0 if visible else 0.2)
    fig.canvas.draw()


def main():
    global max_points
    global fig
    global lined
    global is_magnitude
    parser = ArgumentParser(description="SigMF disp")
    parser.add_argument("-m", "--dB", action="store_true")  # on/off flag
    parser.add_argument("filename", nargs="+")

    args = parser.parse_args()

    is_magnitude = args.dB
    filename: str = args.filename[0]
    collection: Optional[SigMFCollection] = None
    streams = []
    infobox = True
    title = ""
    if len(args.filename) == 1 and filename.endswith(".sigmf-collection"):
        collection_file = sigmffile.fromfile(filename)
        assert isinstance(collection_file, SigMFCollection)
        collection = collection_file
        streams = collection.get_stream_names()
        title = filename
    elif len(args.filename) == 1 and os.path.isdir(filename):
        filename = os.path.join(filename, "recording.sigmf-collection")

        collection_file = sigmffile.fromfile(filename)
        assert isinstance(collection_file, SigMFCollection)
        collection = collection_file
        streams = collection.get_stream_names()
        title = filename
    else:
        title = ", ".join(args.filename)
        if all(fn.endswith(".sigmf-meta") for fn in args.filename):
            collection = SigMFCollection(
                args.filename,
                metadata={
                    "collection": {
                        SigMFCollection.AUTHOR_KEY: "sigmf@sigmf.org",
                        SigMFCollection.DESCRIPTION_KEY: "SigMF",
                    }
                },
            )
            streams = collection.get_stream_names()
        else:
            streams = args.filename
            infobox = False
    if infobox:
        fig, (ax0, ax1) = plt.subplots(
            ncols=2, gridspec_kw={"width_ratios": [7, 2]}, num=title
        )
    else:
        fig, (ax0) = plt.subplots(ncols=1, num=title)
        ax1 = None
    # X axis parameter:
    xaxis = np.array([2, 8])

    # Y axis parameter:
    yaxis = np.array([4, 9])
    ax0.set_title(title)
    global datas
    global lines

    lined = {}  # Will map legend lines to original lines.

    metadata = ""
    sigmf_dirname = os.path.dirname(filename)
    if sigmf_dirname:
        os.chdir(sigmf_dirname)
    for stream in streams:
        if collection is not None:
            signal = collection.get_SigMFFile(stream_name=stream)
            assert isinstance(signal, SigMFFile)
            # signal = sigmffile.fromfile(filename)
            # Get some metadata and all annotations
            sample_rate = signal.get_global_field(SigMFFile.SAMPLE_RATE_KEY)
            sample_count = signal.sample_count
            signal_duration = sample_count / sample_rate
            # Get capture info associated with the start of annotation
            capture = signal.get_capture_info(0)
            freq_center = capture.get(SigMFFile.FREQUENCY_KEY, 0)

            metadata += f"{stream} - {signal_duration:.2f} seconds \n    Count: {sample_count} samples \n    Center: {freq_center/1e6:.3f}M \n    IQ: {sample_rate/1e6:.3f}M\n"

            # Get the samples corresponding to annotation
            samples = signal.read_samples()
        else:
            samples_buf = np.fromfile(stream, np.int16)
            samples = samples_buf.astype(np.float32).view(np.complex64) * (
                1.0 / 32768.0
            )
            metadata += f"{stream} \n"
        lenc = samples.shape[0]
        # print(f"lenc={lenc}")
        i = np.real(samples)
        q = np.imag(samples)

        decimate = max(1, int(lenc // max_points))
        decimate, init_i = downsample(i, decimate)
        decimate, init_q = downsample(q, decimate)

        x_range = np.arange(0, init_i.shape[0] * decimate, decimate)

        (linei,) = ax0.plot(x_range, init_i, lw=2, alpha=0.9)
        linei.set_label(f"{stream} - I")
        (lineq,) = ax0.plot(x_range, init_q, lw=1, alpha=0.9)
        lineq.set_label(f"{stream} - Q")
        if is_magnitude:
            ax0.yaxis.set_major_formatter(  # type: ignore
                mpl.ticker.FuncFormatter(lambda x, _: f"{x:.2f}dB")  # type: ignore
            )
            ax0.set_ylim(-100.0, 0.0)  # set the ylim to bottom, top
        else:
            ax0.set_ylim(-1.0, 1.0)  # set the ylim to bottom, top

        if "_N" in stream:
            linei.set_color("#eeee00")
            lineq.set_color("#999900")
        if "_E" in stream:
            linei.set_color("#00ee00")
            lineq.set_color("#009900")
        if "_S" in stream:
            linei.set_color("#0000ee")
            lineq.set_color("#000099")
        if "_W" in stream:
            linei.set_color("#ee0000")
            lineq.set_color("#990000")

        lines.append(linei)
        lines.append(lineq)
        datas.append(i)
        datas.append(q)

        ax0.callbacks.connect("xlim_changed", ax_update)
        ax0.callbacks.connect("ylim_changed", ax_update)

    leg = ax0.legend(fancybox=True, shadow=True)
    for legline, origline in zip(leg.get_lines(), lines):
        legline.set_marker("*")  # Enable picking on the legend line.
        legline.set_markersize(10)  # Enable picking on the legend line.
        legline.set_picker(10)  # Enable picking on the legend line.
        lined[legline] = origline

    fig.canvas.mpl_connect("pick_event", on_pick)
    if infobox:
        assert ax1 is not None
        ax1.text(
            0,
            1,
            metadata,
            horizontalalignment="left",
            verticalalignment="top",
            transform=ax1.transAxes,
        )
        # hide x-axis
        ax1.get_xaxis().set_visible(False)

        # hide y-axis
        ax1.get_yaxis().set_visible(False)
        ax1.axis("off")

    plt.show()


if __name__ == "__main__":
    main()
