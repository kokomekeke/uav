
"""
Tool for repeatable testing and demonstrating pysagax-uav's
detection and event generation. 

* Plots the spectrogram recording
* Runs and configures PysagaxUAV
* Displays the output of PysagaxUAV
"""

import os
import sys
import subprocess
import click
# from  threading import Thread
from  multiprocessing import Process as Thread
from time import sleep, time
import pysagax.message.command_pb2  as proto_cmd
import pysagax.message.data_pb2  as proto_data

from pysagax.util.get_ip import get_ip
from pysagax.communication.broadcast import RX
from pysagax.communication.pub_sub import SUB
from pysagax.communication.req_rep_tcp import REQ
from pysagax.message.data_types import DataType

from colorclass import Color
import terminaltables


redraw_console = True

first_measurement_ts = None
first_measurement_actual = None
max_drift = 0.
min_drift = 0.

def plot_spectrogram(spectrogram_file):

    subprocess.run(
        ["python", "tools/spectrogram_recordings/spectrogram_viewer.py", "-p", spectrogram_file],
        check=True,
        stdout = subprocess.DEVNULL if redraw_console else None, 
        stderr = subprocess.DEVNULL if redraw_console else None
    )


def pysagax_uav(spectrogram_file):

    subprocess.run(['python', 'pysagax/pysagax_uav.py', '--spectrogram-mode', 'playback', '--spectrogram-path',
                     spectrogram_file, '--level', 'INFO' if redraw_console else 'DEBUG'],
                       check=True, 
                       stdout = subprocess.DEVNULL if redraw_console else None, 
                       stderr = subprocess.DEVNULL if redraw_console else None)


def command(address: str = "127.0.0.1", 
            port: int = 5556,
            own_port: int = 6969,
            roi_centers: list = [],
            roi_spans: list = [],
            roi_thresholds: list = []) -> None:
    cmd_zmq = REQ(address_server=address, port_server=port)
    cmd_zmq.connect()
    cmd_stream_start = proto_cmd.Command()
    cmd_stream_start.instruction = proto_cmd.STREAM_START
    # TODO: customazible stream levels
    cmd_stream_start.target.id = 100
    cmd_stream_start.target.level = proto_cmd.StreamTarget.StreamLevel.SPECTRUM
    cmd_stream_start.target.address = get_ip(address)
    cmd_stream_start.target.port = own_port

    # TODO: think about ideal timeout values, move to config
    cmd_stream_start.target.heartbeat_timeout = 1
    cmd_stream_start.target.telemetry_timeout = 1
    print(cmd_stream_start)
    print("Answer:", proto_cmd.Response.FromString(cmd_zmq.send(cmd_stream_start.SerializeToString(), timeout=2000)))



    cmd_roi = proto_cmd.Command()
    cmd_roi.instruction = proto_cmd.CONFIG
    for i, (c, s, t) in enumerate(zip(roi_centers, roi_spans, roi_thresholds)):
        roi = proto_cmd.ROIMask(roi_id = i, center_frequency=c, span=s, threshold=t)
        cmd_roi.config.pp.roi.append(roi)
    cmd_roi.config.pp.mean_window = 1
    print(cmd_roi)
    print("Answer:", proto_cmd.Response.FromString(cmd_zmq.send(cmd_roi.SerializeToString(), timeout=2000)))
    sleep(5)
    


def stream():

    all_groups = [group.value for group in DataType]
    # client: RX | SUB = SUB(address, port) if address else RX(port)
    client = RX(6969)
    client.connect(group=all_groups)

    global first_measurement_ts
    global first_measurement_actual

    while True:
        data, data_type = client.recv() or (b"*", "*")
        if data_type == "*":
            continue
        data_type_object = DataType(data_type)
        stream_packet = DataType.to_message(data_type_object)
        stream_packet.ParseFromString(data)
        if isinstance(stream_packet, proto_data.Measurement):
            if first_measurement_ts is None:
                first_measurement_ts = stream_packet.time.ToNanoseconds() / 1e9
                first_measurement_actual = time()
            for data in stream_packet.data:
                data.data = f"({len(data.data)} bytes)".encode()
            print_measurement(stream_packet)
    
def print_measurement(m: proto_data.Measurement):
    global redraw_console
    if redraw_console:
        print(chr(27) + "[2J") #clear terminal
        print("\033[1;1H") # move cursor to upper left corner of terminal
    else:
        print("\n\n\n\n\n\n\n")

    print_time_info(m)

    m_table_data = [
        ["time", "stream_id", "config_id", "packet_id", "overflow", "peaks"],
        [m.time, m.stream_id, m.config_id, m.packet_id, m.overflow, m.peaks]
    ]
    m_table = terminaltables.DoubleTable(m_table_data, Color("{autogreen}Measurement{/autogreen}"))
    print(m_table.table)

    d_table_data = [[Color("{autogreen}No.{/autogreen}"),
        "event_id", "roi_id", "freq        ", "bandwidht", "strength", "snr        ", "azimuth (last, mean, deviation)", "mean_window"
    ]]
    for i, d in enumerate(m.detection):
        d_table_data.append([
            i, d.event_id, d.roi_id, f"{f'{d.frequency:,.0f}'.replace(',', ' ')}", d.bandwidth, f"{d.strength:.1f}dB", f"{d.snr:.1f}dB", f"{angle_str(d.azimuth)}, {angle_str(d.mean_azimuth)},{angle_str(d.deviation)}", d.mean_window
        ])
    d_table = terminaltables.SingleTable(d_table_data, Color("{autogreen}DETECTIONS{/autogreen}"))
    d_table.inner_row_border = True
    d_table.inner_heading_row_border = False
    print(d_table.table)




    # m.

    fields = [field.name for field in proto_data.Event.DESCRIPTOR.fields]
    e_table_data = [[Color("{autogreen}No.{/autogreen}")]+fields]

    e_table = terminaltables.SingleTable(e_table_data, Color("{autogreen}EVENTS{/autogreen}"))
    e_table.inner_row_border = True
    e_table.inner_heading_row_border = False
    print(e_table.table)

def print_time_info(m):
    global max_drift
    global min_drift

    elapsed_packet_t = m.time.ToNanoseconds()/1e9 - first_measurement_ts
    elapsed_actual = time() - first_measurement_actual
    drift =elapsed_packet_t - elapsed_actual
    max_drift = max(drift, max_drift)
    min_drift = min(drift, min_drift)
    print(f"Elapsed (packet / actual): "
          f"{elapsed_packet_t:6.2f} / "
          f"{elapsed_actual:6.2f}"
          f"\t\tdrift: {drift:6.2f}\tmax/min drift: {max_drift:6.2f} / {min_drift:6.2f}\n\n")

def angle_str(angle):
    return f"{angle*180/3.1415926535897932384626:8.2f}°"

@click.command()
@click.option(
    "-id",
    "--spectrogram-id",
    type=int,
    required = False,
    help="Id of pre-recorded spectrogram-files and corresponding ROI masks (0..4)",
)
@click.option(
    "-16k", "bc_16k",
    type=bool,
    required = False,is_flag=True, show_default=True, default=False,
    help="Use the 16k bin count  recs instead of the default 1k ones",
)
@click.option(
    "--spectrogram-file", "file_path",
    type=str,
    required = False,
    help="Location of custom spectrogram-files. Can still use -id flag to specify a ROI mask from the defaults (0..4)",
)
@click.option(
    "-v", "verbose",
    type=bool,
    required = False,is_flag=True, show_default=False, default=False,
    help="Do not supress the output of subprocesses and redraw console",
)
@click.option(
    "-np", "no_plot",
    type=bool,
    required = False,is_flag=True, show_default=False, default=False,
    help="Do not plot the spectrograms",
)
def main(spectrogram_id: int = None, bc_16k: bool = False, file_path: str = None, verbose: bool = False, no_plot:bool=False):
    global redraw_console
    redraw_console = not verbose

    bin_count = "16k" if bc_16k else "1k"
    spectrum_options = [
                "/media/rp/data/recordings/20231113_Mon_130503/",
                "/media/rp/data/recordings/20231113_Mon_141230/",
                "/media/rp/data/recordings/20231113_Mon_141725/",
                "/media/rp/data/recordings/20240229_Thu_134948/",
                "/media/rp/data/recordings/20240229_Thu_135712/",]
    if file_path is None:
        spectrogram_file = f"{spectrum_options[spectrogram_id]}spectrogram-{bin_count}.protorec"
    else:
        spectrogram_file = file_path
    print(spectrogram_file)
    
    match spectrogram_id:
        case 0:
            roi_cst = [
                # [],
                # [],
                # [],
            ]
        case 1:
            roi_cst = [
                [445.9e6, 100e3, -60],
                [446.08e6,20e3,-60],
            ]
        case 2:
            roi_cst = [
                [445.9e6, 100e3, -58],
                [446.08e6, 20e3,-58], # weak, present most of the time
                [446.0185e6, 10e3, -58], #few strong bursts
                [446.181e6, 20e3, -79], #short and weak burst from 69 to 72 secs
            ]
        case 3:
            roi_cst = [
                # [],
                # [],
                # [],
            ]
        case 4:
            roi_cst = [
                # [],
                # [],
                # [],
            ]
    roi_centers = [roi[0] for roi in roi_cst]
    roi_spans = [roi[1] for roi in roi_cst]
    roi_thresholds = [roi[2] for roi in roi_cst]
    roi_dict = {"roi_centers": roi_centers, "roi_spans": roi_spans, "roi_thresholds":roi_thresholds}


    # spectrogram_file ="/media/rp/data/recordings/20231113_Mon_141230/spectrogram-16k.protorec"
    if not no_plot:
        print("Plotting Spectrogram. Please wait patiently")
        plot_thread = Thread(target=plot_spectrogram, args=[spectrogram_file])
        plot_thread.start()
        # plot_spectrogram(spectrogram_file)
        # print("Spectrogram plotted")
        sleep(14 if bc_16k else 5)

    pysagax_thread = Thread(target=pysagax_uav, args=[spectrogram_file])
    pysagax_thread.start()

    print("pysagax running")
    command_thread = Thread(target=command, kwargs = roi_dict)
    command_thread.start()
    
    stream_thread = Thread(target=stream)
    stream_thread.start()


if __name__ == "__main__":
    main()