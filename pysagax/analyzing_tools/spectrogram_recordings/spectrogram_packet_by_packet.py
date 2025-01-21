import click
import pysagax.message.data_pb2 as proto_data
from pysagax.message.proto_stream_to_file import FileStreamer
from pysagax.util.protobuf_spectrum_utils import protobuf_spectrum_to_numpy
import numpy as np

from colorclass import Color




@click.command()
@click.option(
    "-p",
    "--path",
    type=str,
    required = True,
    help="Location for the .protorec file that is to be displayed",
)
@click.option(
    "-v",
    "--verbose",
    type=bool,
    required = False,is_flag=True, show_default=False, default=False,
    help="Print out more info", 
)
def main(path:str, verbose: bool):
    """
    Reads a .protorec file, and prints out the most important details of each Measurement packet inside it.
    Highlights unusual values. (eg 0 peak values)
    """
    file_streamer = FileStreamer(path, mode="playback")
    
    while True:
        packet: proto_data.Measurement = file_streamer.get()
        if not isinstance(packet, proto_data.Measurement):
            if verbose:
                print(f"Packet type '{type(packet)}' is not supported")
            continue
              
        for data in packet.data:
            data_np = protobuf_spectrum_to_numpy(data)

            data_max = data_np.max()
            max_str = f"max={data_max:7.2f}" if np.isfinite(data_max) else Color("{autored}\033[1m" + f"max={data_max:7.2f}".upper() + "\033[0m{/autored}")
            data_min = data_np.min()
            min_str = f"min={data_min:7.2f}" if np.isfinite(data_min) else Color("{autored}\033[1m" + f"min={data_min:7.2f}".upper() + "\033[0m{/autored}")
            data_nan = np.count_nonzero(np.isnan(data_np))
            nan_str = f"nans={data_nan}" if data_nan == 0 else Color("{autored}\033[1m" + f"nans={data_nan}".upper() + "\033[0m{/autored}")

            data.data = (f"({len(data.data)} bytes = {len(data_np)} values, {max_str}, {min_str}, {nan_str}) ").encode()
        # print(packet)

        peaks_str = ','.join([f'{p:3}' for p in packet.peaks])
        if any([not np.isfinite(p) or p == 0 for p in packet.peaks]):
             peaks_str = Color("{autored}\033[1m" + peaks_str + "\033[0m{/autored}")
        
        print(Color("CF = {autored}\033[1m" + f"{packet.data[0].center_frequency/1e6:6.2f}" + "\033[0m{/autored}" + f", SPAN = {packet.data[0].bandwidth/1e6:5.2f}"),
              Color("{automagenta}PEAKS{/automagenta}=[" + peaks_str + "] >>> "),
              Color("{autogreen}" + f"{proto_data.Spectrum.SpectrumType.Name(packet.data[0].spectrum_type)}" + "{/autogreen}") + f"-{packet.data[0].data.decode()}",
              Color("{autogreen}" + f"{proto_data.Spectrum.SpectrumType.Name(packet.data[1].spectrum_type)}" + "{/autogreen}") + f"-{packet.data[1].data.decode()}",
              Color("{autogreen}" + f"{proto_data.Spectrum.SpectrumType.Name(packet.data[2].spectrum_type)}" + "{/autogreen}") + f"-{packet.data[2].data.decode()}"
            #   f"{proto_data.Spectrum.SpectrumType.Name(packet.data[1].spectrum_type)}-{packet.data[1].data}"
            #   f"{proto_data.Spectrum.SpectrumType.Name(packet.data[2].spectrum_type)}-{packet.data[2].data}"
              , end="")
        q = input()
        if q == "q":
             break

if __name__ == "__main__":
    main()
