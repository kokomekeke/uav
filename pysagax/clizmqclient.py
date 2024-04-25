#!/usr/bin/env python3

import click
import logging

from pysagax.communication.broadcast import RX
from pysagax.communication.pub_sub import SUB
import pysagax.message.data_pb2 as proto_data

from pysagax.message.data_types import DataType


@click.command()
@click.option("-p", "--port", type=int, default=5050, help="Port of receiver")
@click.argument("address", default="", required=False)
def main(port: int = 5050, address: str = ""):
    logging.basicConfig(level="DEBUG")
    logging.getLogger("main")
    if address:
        print(f"ZMQ SUB connecting on {address}:{port}/tcp ZMQ PUB")
    else:
        print(f"ZMQ DISH on port {port}/udp waiting for ZMQ RADIO")
    all_groups = [group.value for group in DataType]
    client: RX | SUB = SUB(address, port) if address else RX(port)
    client.connect(group=all_groups)

    while True:
        data, data_type = client.recv() or (b"*", "*")
        if data_type == "*":
            continue
        data_type_object = DataType(data_type)
        stream_packet = DataType.to_message(data_type_object)
        stream_packet.ParseFromString(data)
        if isinstance(stream_packet, proto_data.Measurement):
            for data in stream_packet.data:
                data.data = f"({len(data.data)} bytes)".encode()
        print(f"--- {data_type} -> {data_type_object.name}")
        print(stream_packet)


if __name__ == "__main__":
    main()
