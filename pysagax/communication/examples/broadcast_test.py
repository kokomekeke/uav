#!/usr/bin/env python3

import click
import random
import logging
import time

from pysagax.communication.broadcast import TX, RX


INDEX_SIZE = 4
TIMESTAMP_SIZE = 8


def tx(
        address: str = "127.0.0.1",
        port: int = 5050,
        number: int | None = 1000,
        size: int = 4048,
        sleep: float | None = 0.1
):
    print("Transmitting")
    server = TX(address=address, port=port)
    server.connect()

    i = 0
    while number is None or i < number:
        timestamp = time.time_ns()

        header = i.to_bytes(INDEX_SIZE, byteorder="little") \
                +timestamp.to_bytes(TIMESTAMP_SIZE, byteorder="little")

        data = random.randbytes(size-len(header))
        print(f"Sending data    index {i:<6}    data: {len(data)} bytes")
        server.send(header+data, group="b")

        i += 1

        if sleep is not None:
            time.sleep(sleep)


def rx(
        port: int = 5050,
        number: int | None = 1000
):
    print("Receiving")
    client = RX(port=port, groups=["b"])
    client.connect()

    i = 1
    while number is None or i < number:
        data, group = client.recv()

        index = int.from_bytes(
            data[:INDEX_SIZE], byteorder="little"
        )
        timestamp = int.from_bytes(
            data[INDEX_SIZE:INDEX_SIZE+TIMESTAMP_SIZE], byteorder="little"
        )
        data = data[INDEX_SIZE+TIMESTAMP_SIZE:]

        delay = (time.time_ns()-timestamp)/1e6

        print(f"Received data    index: {index:<6}    group: {group}    data: {len(data)} bytes    delay: {delay:<02.4f} ms")

        i += 1


@click.command()
@click.option(
    "-tx", "--transmit", "mode",
    is_flag=True, flag_value="tx",
    required=True
)
@click.option(
    "-rx", "--receive", "mode",
    is_flag=True, flag_value="rx",
    required=True
)
@click.option(
    "-a", "--address",
    default="127.0.0.1",
    help="IP address of receiver"
)
@click.option(
    "-p", "--port",
    type=int, default=5050,
    help="Port of receiver"
)
@click.option(
    "-n", "--number",
    type=int, default=1000,
    help="Number of messages to send/receive. Only if --loop is not set"
)
@click.option(
    "-l", "--loop",
    is_flag=True,
    help="Loop indefinitely"
)
@click.option(
    "-s", "--size",
    type=int, default=4048,
    help="Size of messages in bytes"
)
def main(
        mode: str,
        address: str = "127.0.0.1",
        port: int = 5050,
        number: int = 1000,
        loop: bool = False,
        size: int = 4048
    ):
    logging.basicConfig(
        level="DEBUG"
    )
    logging.getLogger("main")

    if loop:
        number = None
    match mode:
        case "tx":
            tx(
                address=address,
                port=port,
                number=number,
                size=size,
            )
        case "rx":
            rx(
                port=port,
                number=number,
            )
        case _:
            print("Unknown command")


if __name__ == '__main__':
    main()
