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
from sigmf import SigMFFile, sigmffile

max_points = 1000
datas = []
lines = []


def downsample(y, decim):
    # total_decim = 1
    # if decim > 1:
    #     while decim > 10:
    #         if decim % 2 != 0:
    #             decim += 1
    #         if decim % 4 == 0:
    #             y = sg.decimate(y, 4, ftype="iir")
    #             decim = decim // 4
    #             total_decim *= 4
    #         else:
    #             y = sg.decimate(y, 2, ftype="iir")
    #             decim = decim // 2
    #             total_decim *= 2
    #
    #     total_decim *= decim
    #     return total_decim, sg.decimate(y, decim, ftype="iir")
    # else:
    if decim == 1:
        return 1, y
    new_len = y.shape[0] // decim
    z = np.zeros(new_len)
    stat_len = decim * 2
    # print(f"Downsample new len {new_len} stat_len {stat_len}")
    for i in range(0, new_len - 1, 2):
        i_start = i * decim
        i_end = min(i_start + stat_len - 1, y.shape[0])
        stat_range = y[i_start:i_end]
        z[i] = np.min(stat_range)
        z[i + 1] = np.max(stat_range)
    return decim, z


def ax_update(event_ax):
    new_lim = int(max(0, event_ax.get_xlim()[0])), int(
        min(len(datas[0]), event_ax.get_xlim()[1])
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
    parser = ArgumentParser(description="SigMF disp")

    parser.add_argument("filename")
    args = parser.parse_args()
    filename = args.filename

    if os.path.isdir(filename):
        filename = os.path.join(filename, "recording.sigmf-collection")

    collection = sigmffile.fromfile(filename)
    streams = collection.get_stream_names()

    fig, (ax0, ax1) = plt.subplots(
        ncols=2, gridspec_kw={"width_ratios": [7, 2]}, num="CS SigMF File Viewer"
    )

    # X axis parameter:
    xaxis = np.array([2, 8])

    # Y axis parameter:
    yaxis = np.array([4, 9])
    ax0.set_title(filename)
    global datas
    global lines

    lined = {}  # Will map legend lines to original lines.

    metadata = ""
    os.chdir(os.path.dirname(filename))
    for stream in streams:
        signal = collection.get_SigMFFile(stream_name=stream)
        # signal = sigmffile.fromfile(filename)
        # Get some metadata and all annotations
        sample_rate = signal.get_global_field(SigMFFile.SAMPLE_RATE_KEY)
        sample_count = signal.sample_count
        signal_duration = sample_count / sample_rate
        # Get capture info associated with the start of annotation
        capture = signal.get_capture_info(0)
        freq_center = capture.get(SigMFFile.FREQUENCY_KEY, 0)
        freq_min = freq_center - 0.5 * sample_rate
        freq_max = freq_center + 0.5 * sample_rate

        metadata += f"{stream} - {signal_duration:.2f} seconds \n    Count: {sample_count} samples \n    Center: {freq_center/1e6:.3f}M \n    IQ: {sample_rate/1e6:.3f}M\n"

        # Get the samples corresponding to annotation
        samples = signal.read_samples()
        lenc = samples.shape[0]
        # print(f"lenc={lenc}")
        i = np.real(samples)
        q = np.imag(samples)

        decimate = lenc // max_points
        decimate, init_i = downsample(i, decimate)
        decimate, init_q = downsample(q, decimate)

        x_range = np.arange(0, init_i.shape[0] * decimate, decimate)

        (linei,) = ax0.plot(x_range, init_i, lw=2, alpha=0.9)
        linei.set_label(f"{stream} - I")
        (lineq,) = ax0.plot(x_range, init_q, lw=1, alpha=0.9)
        lineq.set_label(f"{stream} - Q")
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
