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
from  matplotlib import pyplot as plt

def plot_spectrogram(meta, spectrogram, timestamps, radians=False, ax_to_share=None, threshold = None):
    s_type = proto_data.Spectrum.SpectrumType.Name(meta["type"])
    center_freq = meta["center_frequency"]
    span = meta["span"]
    channel = meta["channel"]


    #TODO: insert nans in spectrogram if no data for long time and provide the timestamp list to this funciion
    #TODO: check if plot time axes is pointing in the correct way, and also its labels are correct
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)

    f_min = center_freq-span/2
    f_max = center_freq+span/2

    # threshold = None
    # threshold = -75
    if threshold is not None:
        spectrogram[spectrogram < threshold] = np.nan

    #TODO
    t_min = 0
    # t_max = 100
    t_max = timestamps[-1] - timestamps[0]

    if meta["type"] == proto_data.Spectrum.SpectrumType.MAGNITUDE:
        db_min = -120
        db_max = 0
        cmap = matplotlib.colormaps.get_cmap("gnuplot")
        spectrogram = spectrogram *1
    else: # for azimuth and elevation spectrums
        if radians:
            db_max = np.pi
            db_min = -np.pi
        else: #plot degree values
            db_max = 180
            db_min = -180
            spectrogram = spectrogram*180/np.pi

        cmap = matplotlib.colormaps.get_cmap("hsv")
        # cmap = matplotlib.colormaps.get_cmap("twilight")
    fig, ax = plt.subplots()
    fig.suptitle(f"{s_type}: cf = {center_freq:.2e}Hz; span = {span:.2e}Hz; channel_id = {channel}")
    show = ax.imshow if threshold is None else ax.matshow
    image = show(#ax.imshow( # use matshow() for no anti aliasing!
        spectrogram,
        cmap=cmap,  # type: ignore
        animated=True,
        vmax=db_max,
        vmin=db_min,
        aspect='auto', extent=[f_min,f_max, t_min, t_max]
    )
    # plt.yticks(timestamps, rotation="vertical")
    plt.colorbar(image) 
    if  ax_to_share is not None:
        ax_to_share.sharey(ax)
        ax_to_share.sharex(ax)


    plt.subplots_adjust(bottom=0.25)
    from matplotlib.widgets import Slider
    ax_slider = plt.axes([0.1, 0.1, 0.8, 0.03])
    slider = Slider(ax_slider, 'Threshold', -100, 0, valinit=-79,)# orientation="vertical")
    slider.on_changed(lambda val:update(val, spectrogram, slider, image, fig))
    ax.format_coord = format_coord
    return ax

def update(val, spectrogram, slider, im, fig):
    threshold = slider.val
    masked_data = np.where(spectrogram > threshold, spectrogram, np.nan)
    im.set_data(masked_data)
    fig.canvas.draw_idle()

def format_coord(x, y):
    "Custom formatting: x: triple grouped digits rounded to Hz"
    return f'x={f"{x:,.0f}".replace(",", " ")} Hz, y={y:.2f} s'



def plot_spectrogram3(meta, spectrogram, timestamps, radians=False):

    from matplotlib.image import NonUniformImage
    s_type = proto_data.Spectrum.SpectrumType.Name(meta["type"])
    center_freq = meta["center_frequency"]
    span = meta["span"]
    channel = meta["channel"]
    bin_count = spectrogram.shape[1]


    #TODO: insert nans in spectrogram if no data for long time and provide the timestamp list to this funciion
    #TODO: check if plot time axes is pointing in the correct way, and also its labels are correct
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)
    # spectrogram = np.insert(spectrogram, 20, np.nan, axis=0)

    f_min = center_freq-span/2
    f_max = center_freq+span/2

    #TODO
    t_min = 0
    t_max = 100

    if meta["type"] == proto_data.Spectrum.SpectrumType.MAGNITUDE:
        db_min = -120
        db_max = 0
        cmap = matplotlib.colormaps.get_cmap("gnuplot")
    else: # for azimuth and elevation spectrums
        if radians:
            db_max = np.pi
            db_min = -np.pi
        else: #plot degree values
            db_max = 180
            db_min = -180
            spectrogram = spectrogram*180/np.pi

        cmap = matplotlib.colormaps.get_cmap("hsv")
    fig, ax = plt.subplots()
    fig.suptitle(f"NONUNIFORM{s_type}: cf = {center_freq:.2e}Hz; span = {span:.2e}Hz; channel_id = {channel}")
    
    # x = np.linspace(f_min, f_max, bin_count+1, endpoint=True)
    x = np.linspace(f_min, f_max, bin_count, endpoint=True)
    y = timestamps
    # y.append(y[-1] + y[-1] - y[-2])
    print(spectrogram.shape, len(x), len(y))
    im = NonUniformImage(ax, extent=[f_min,f_max, t_min, t_max],cmap=cmap)
    # im.set_data(x, y, spectrogram)
    im.set_data(y, x, spectrogram.transpose())
    ax.add_image(im)
    # ax.images.append(im)

    # image = ax.imshow(
    #     spectrogram,
    #     cmap=cmap,  # type: ignore
    #     animated=True,
    #     vmax=db_max,
    #     vmin=db_min,
    #     aspect='auto', extent=[f_min,f_max, t_min, t_max]
    # )
    # plt.yticks(timestamps, rotation="vertical")
    # plt.colorbar(image) 
    

def plot_spectrogram2(meta, spectrogram, timestamps):
    s_type = proto_data.Spectrum.SpectrumType.Name(meta["type"])
    center_freq = meta["center_frequency"]
    span = meta["span"]
    channel = meta["channel"]
    bin_count = spectrogram.shape[1]

    f_min = center_freq-span/2
    f_max = center_freq+span/2

    #TODO
    t_min = 0
    t_max = 100

    if meta["type"] == proto_data.Spectrum.SpectrumType.MAGNITUDE:
        db_min = -120
        db_max = 0
        cmap = matplotlib.colormaps.get_cmap("gnuplot")
    else: # for azimuth and elevation spectrums
        db_max = np.pi
        db_min = -np.pi
        cmap = matplotlib.colormaps.get_cmap("hsv")

    x = np.linspace(f_min, f_max, bin_count+1, endpoint=True)
    y = timestamps
    y.append(y[-1] + y[-1] - y[-2])
    # print("BINC", bin_count)
    # print(x)
    # print(y)
    X,Y = np.meshgrid(x, y)

    fig, ax = plt.subplots()
    fig.suptitle(f"{s_type}: cf = {center_freq:.2e}Hz; span = {span:.2e}Hz; channel_id = {channel}")

    plt.xticks(x), 
    plt.yticks(y)
    image = ax.pcolormesh(X, Y, spectrogram, cmap=cmap)

    plt.clabel(image, inline=1, fontsize=10)
    plt.colorbar(image) 


    

    # fig, ax = plt.subplots()
    # fig.suptitle(f"{s_type}: cf = {center_freq:.2e}Hz; span = {span:.2e}Hz; channel_id = {channel}")
    # image = ax.imshow(
    #     spectrogram,
    #     cmap=cmap,  # type: ignore
    #     animated=True,
    #     vmax=db_max,
    #     vmin=db_min,
    #     aspect='auto', extent=[f_min,f_max, t_min, t_max]
    # )
    # plt.yticks(timestamps, rotation="vertical")
    # plt.colorbar(image) 


@click.command()
@click.option(
    "-p",
    "--path",
    type=str,
    required = True,
    help="Location for the .protorec file that is to be displayed",
)
@click.option(
    "-t",
    "--threshold",
    type=float,
    default=None,
    required = False,
    help="Replace values below this with nan",
)
@click.option("--radians", "-r", is_flag=True, show_default=True, default=False,
              help="Plot azimuth and elevation spectrograms using radian values")
def main(path:str, radians:bool, threshold = None):
    # file_streamer = FileStreamer("pysagax/gany/proto_file_stream/recordings/test_scan.protorec", "playback")
    # file_streamer = FileStreamer("pysagax/gany/proto_file_stream/recordings/test_float16_65k-65k_20240606_125722.protorec", "playback")
    file_streamer = FileStreamer(path, mode="playback")

    start = time()
    time_list, packet_list = file_streamer.read_all()
    print("FINISH: ", time()- start)

    # print(packet_list)

    # spectrum_width = 

    spectrogram_meta_list = []
    spectrogram_list = []
    timestamp_lists = []

    start = time()
    for packet, ts in zip(packet_list, time_list):
        # separate packet list into spectrograms of different channels, types (magnitude or angle), and spans and bandwidths
        if not isinstance(packet, proto_data.Measurement):
            continue
        for spectrum in packet.data:
            meta = {"type": spectrum.spectrum_type,
                    "center_frequency": spectrum.center_frequency,
                    "span": spectrum.bandwidth,
                    "channel": spectrum.channel_id,
                    "spectrum_bytes": len(spectrum.data)}
            try:
                index = spectrogram_meta_list.index(meta)
            except ValueError:
                print("NEW")
                spectrogram_meta_list.append(meta)
                index = len(spectrogram_meta_list) - 1 
                spectrogram_list.append([])
                timestamp_lists.append([])
            
            spectrum_np = protobuf_spectrum_to_numpy(spectrum)
            spectrogram_list[index].append(spectrum_np)
            timestamp_lists[index].append(ts)
            
            
    print("FINISH: ", time()- start, )#spectrogram.shape, len(packet_list))

    print(len(spectrogram_list))

    # Lists of pyplot axes of spectrograms that cover the same part of the RF spectrum
    #   for sharing their X and Y axis so that they pan and zoom together
    ax_dict = {} 

    # for meta, spectrogram, timestamps in zip(spectrogram_meta_list, spectrogram_list, timestamp_lists):
    for meta, spectrogram, timestamps in zip(reversed(spectrogram_meta_list), reversed(spectrogram_list), reversed(timestamp_lists)):
        spectrogram_np = np.array(spectrogram[::-1])
        
        xticks = timestamps
        # xticks  = [i for i in range(spectrogram_np.shape[0])]
        # print(spectrogram_np.shape, spectrogram_np.shape[1], xticks)
        ax_key = (meta["center_frequency"], meta["span"])
        if ax_key in ax_dict:
            ax_to_share = ax_dict[ax_key][-1]
        else:
            ax_to_share = None
            ax_dict[ax_key] = []

        #only use threshold for magnitude spectrums
        th = threshold if  meta["type"] == proto_data.Spectrum.SpectrumType.MAGNITUDE else None
        print(th)
        ax = plot_spectrogram(meta, spectrogram_np, xticks, radians, ax_to_share, threshold=th)

        ax_dict[ax_key].append(ax)

        # plot_spectrogram3(meta, spectrogram_np, xticks, radians)




    plt.show(block=True)    



if __name__ == "__main__":
    main()
