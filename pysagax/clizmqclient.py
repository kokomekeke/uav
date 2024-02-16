#!/usr/bin/env python3

import click
import logging

from pysagax.communication.broadcast import RX
import pysagax.message.data_pb2 as proto_data


@click.option("-p", "--port", type=int, default=5050, help="Port of receiver")
def main(
    port: int = 5050,
):
    logging.basicConfig(level="DEBUG")
    logging.getLogger("main")
    client = RX(port=port, groups=["*"])
    client.connect()

    while True:
        data = client.recv()
        meas_packet = proto_data.Measurement()
        meas_packet.ParseFromString(data)
        for data in meas_packet.data:
            data.data = f"({len(data.data)} bytes)".encode()
        print(meas_packet)
        print("---")


if __name__ == "__main__":
    main()
