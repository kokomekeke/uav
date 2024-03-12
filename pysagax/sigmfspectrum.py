#!/usr/bin/env python3
# This tool is for displaying and saving the spectrum of SigMF recordings

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os
import scipy
import click

# from scipy import signal as sg
from sigmf import SigMFFile, SigMFCollection, sigmffile

"""
Fast Plotter for Large Images - Resamples Images to a target resolution on each zoom.
Example::
    sz = (10000,20000) # rows, cols
    buf = np.arange(sz[0]*sz[1]).reshape(sz)
    extent = (100,150,1000,2000)
    fig = plt.figure()
    ax  = fig.add_subplot(111)
    im = FastImshow(buf,extent,ax)
    im.show()
    plt.show()
"""

import numpy as np
import matplotlib.pyplot as plt


class FastImshow:
    """
    Fast plotter for large image buffers
    Example::
        sz = (10000,20000) # rows, cols
        buf = np.arange(sz[0]*sz[1]).reshape(sz)
        extent = (100,150,1000,2000)
        fig = plt.figure()
        ax  = fig.add_subplot(111)
        im = FastImshow(buf,extent,ax)
        im.show()
        plt.show()
    """

    def __init__(self, buf, ax, extent=None, tgt_res=512):
        """
        [in] img buffer
        [in] extent
        [in] axis to plot on
        [in] tgt_res(default=512) : target resolution
        """
        self.buf = buf
        self.sz = self.buf.shape
        self.tgt_res = tgt_res
        self.ax = ax

        # Members required to account for mapping extent to buf coordinates
        if extent:
            self.extent = extent
        else:
            self.extent = [0, self.sz[1], 0, self.sz[0]]
        self.startx = self.extent[0]
        self.starty = self.extent[2]
        self.dx = self.sz[1] / (self.extent[1] - self.startx)  # extent dx
        self.dy = self.sz[0] / (self.extent[3] - self.starty)  # extent dy

    # end __init__

    def get_strides(self, xstart=0, xend=-1, ystart=0, yend=-1, tgt_res=512):
        """
        Get sampling strides for a given bounding region. If none is provided,
           use the full buffer size
        """
        # size = (rows,columns)
        if xend == -1:
            xend = self.sz[1]
        if yend == -1:
            yend = self.sz[0]
        if (xend - xstart) <= self.tgt_res:
            stridex = 1
        else:
            stridex = max(int((xend - xstart) / self.tgt_res), 1)

        if (yend - ystart) <= self.tgt_res:
            stridey = 1
        else:
            stridey = max(int((yend - ystart) / self.tgt_res), 1)

        return stridex, stridey

    # end get_strides

    def ax_update(self, ax):
        """
        Event handler for re-plotting on zoom
        - gets bounds in img extent coordinates
        - converts to buffer coordinates
        - calculates appropriate strides
        - sets new data in the axis
        """
        ax.set_autoscale_on(False)  # Otherwise, infinite loop

        # Get the range for the new area
        xstart, ystart, xdelta, ydelta = ax.viewLim.bounds
        xend = xstart + xdelta
        yend = ystart + ydelta

        xbin_start = int(self.dx * (xstart - self.startx))
        xbin_end = int(self.dx * (xend - self.startx))
        ybin_start = int(self.dy * (ystart - self.starty))
        ybin_end = int(self.dy * (yend - self.starty))

        # Update the image object with our new data and extent
        im = ax.images[-1]

        stridex, stridey = self.get_strides(xbin_start, xbin_end, ybin_start, ybin_end)

        im.set_data(self.buf[ybin_start:ybin_end:stridey, xbin_start:xbin_end:stridex])

        im.set_extent((xstart, xend, ystart, yend))

        ax.figure.canvas.draw_idle()

    # end ax_update

    def show(self):
        """
        Initial plotter for buffer
        """
        stridex, stridey = self.get_strides()
        self.ax.imshow(
            self.buf[::stridex, ::stridey],
            extent=self.extent,
            origin="lower",
            aspect="auto",
        )
        self.ax.figure.canvas.draw_idle()
        self.ax.yaxis.set_major_formatter(  # type: ignore
            mpl.ticker.FuncFormatter(lambda x, pos: f"{x/1e6:.3f}M")  # type: ignore
        )

        self.ax.callbacks.connect("xlim_changed", self.ax_update)
        self.ax.callbacks.connect("ylim_changed", self.ax_update)

    # end show


# end ImgDisplay


@click.command()
@click.option("--fftsize", default=1024, type=int, help="FFT size")
@click.option("--stride", default=1024, type=int, help="File read stride")
@click.option(
    "--show",
    multiple=True,
    type=int,
    default=[],
    help="Show channels on a plot (ch index)",
)
@click.option(
    "--save",
    multiple=True,
    type=int,
    default=[],
    help="Save channels to a file (ch index)",
)
@click.argument(
    "filename",
    # help="Path to sigmf-collection or containing folder.",
)
def main(fftsize, stride, show, save, filename):
    
    if not show and not save:
        show = [0]
        print("No channel selected for displaying or saving. Selecting channel 0 to display.")
        print("To select one or more channels use options like: --show 0 --show 1 --save 0")
    if os.path.isdir(filename):
        filename = os.path.join(filename, "recording.sigmf-collection")

    collection = sigmffile.fromfile(filename)
    assert isinstance(collection, SigMFCollection)
    streams = collection.get_stream_names()

    os.chdir(os.path.dirname(filename))
    plots_shown = 0
    for index, stream in enumerate(streams):
        if index not in show and index not in save:
            print(f"Skipping {stream}")
            continue

        print(f"Reading {stream}")
        assert collection
        signal_sigmf = collection.get_SigMFFile(stream_name=stream)
        assert isinstance(signal_sigmf, SigMFFile)
        # signal = sigmffile.fromfile(filename)
        # Get some metadata and all annotations
        sample_rate = signal_sigmf.get_global_field(SigMFFile.SAMPLE_RATE_KEY)
        sample_count = signal_sigmf.sample_count
        signal_duration = sample_count / sample_rate
        # Get capture info associated with the start of annotation
        capture = signal_sigmf.get_capture_info(0)
        freq_center = capture.get(SigMFFile.FREQUENCY_KEY, 0)
        print(
            f"{stream} - {signal_duration:.2f} seconds \n    Count: {sample_count} samples \n    Center: {freq_center/1e6:.3f}M \n    IQ: {sample_rate/1e6:.3f}M\n"
        )

        # Get the samples corresponding to annotation
        # samples = signal_sigmf.read_samples()
        samples_ba = bytearray()
        read_samp_count = 0
        stride_count = 0
        with open(str(signal_sigmf.data_file), "rb") as bin_file:
            while read_samp_count + stride <= sample_count:
                a = bin_file.read(fftsize * 4)
                samples_ba += a
                a = bin_file.seek(stride * 4 * stride_count)
                read_samp_count += stride
                stride_count += 1
        reduced_sample_count = len(samples_ba)
        print(f"Read samples {str(signal_sigmf.data_file)} {reduced_sample_count}")
        # print(f"lenc={lenc}")
        samples = (
            np.frombuffer(bytes(samples_ba), dtype="i2")
            .astype(np.float32)
            .view(np.complex64)
        )
        win = scipy.signal.windows.tukey(fftsize, 0.25)  # symmetric Gaussian wind.

        SFT = scipy.signal.ShortTimeFFT(
            win,
            hop=fftsize,
            fs=sample_rate,
            mfft=fftsize,
            # scale_to="psd",
            fft_mode="centered",
            scale_to="magnitude",
        )
        Sxx = SFT.spectrogram(samples)
        # f, t, Sxx = signal.spectrogram(
        #     samples, sample_rate, nperseg=fftsize, return_onesided=False, noverlap=0
        # )
        # Sxx = np.fft.fftshift(Sxx, axes=0)
        # f = np.fft.fftshift(f)
        if index in save:
            np.savez(
                str(signal_sigmf.data_file),
                spectrum=Sxx,
                sample_rate=sample_rate,
                freq_center=freq_center,
                signal_duration_seconds=signal_duration,
                stride=stride,
                sample_count=sample_count,
                reduced_sample_count=reduced_sample_count,
                fftsize=fftsize,
            )
            print(f"Saved npz for {str(signal_sigmf.data_file)}")
        if index in show:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            im = FastImshow(
                    buf=20 * np.log10(Sxx),
                ax=ax,
                extent=[
                    0,
                    sample_count / sample_rate,
                    freq_center - sample_rate / 2,
                    freq_center + sample_rate / 2,
                ],
                tgt_res=1024,
            )
            im.show()
            # plt.plot(samples)
            plots_shown += 1
            plt.get_current_fig_manager().set_window_title(f"{str(stream)} ({index})" )  # type: ignore

            plt.show(block=True if len(show) >= plots_shown else False)
  


if __name__ == "__main__":
    main()
