#!/usr/bin/env python3

import time
import click
import random
import logging

from pysagax.communication.req_rep_tcp import REQ, REP


INDEX_SIZE = 4
TIMESTAMP_SIZE = 8


def generate_message(
        size: int = 4048,
        index: int = 0
):
    timestamp = time.time_ns()

    header = index.to_bytes(INDEX_SIZE, byteorder="little") \
            +timestamp.to_bytes(TIMESTAMP_SIZE, byteorder="little")
    data = random.randbytes(size-len(header))

    return header+data


def decode_message(message: bytes):
    index = int.from_bytes(
        message[:INDEX_SIZE], byteorder="little"
    )
    timestamp = int.from_bytes(
        message[INDEX_SIZE:INDEX_SIZE+TIMESTAMP_SIZE], byteorder="little"
    )
    data = message[INDEX_SIZE+TIMESTAMP_SIZE:]

    return data, index, timestamp


def request(
        address_client: str = "127.0.0.1",
        address_server: str = "127.0.0.1",
        port_client: int = 5555,
        port_server: int = 5556,
        init: bool = False,
        number: int | None = 1000,
        size: int = 4048,
        timeout: int | None = 1000,
        sleep: float | None = 0.1
):
    if not init:
        address_client = None

    print("Request client started")
    client = REQ(
        address_client=address_client,
        address_server=address_server,
        port_client=port_client,
        port_server=port_server
    )

    if not client.connect(timeout=10000):
        print("Could not connect")

        return

    i = 0
    while number is None or i < number:
        message = generate_message(size=size, index=i)
        print(f"Sending message    index {i:<6}    message: {len(message)} bytes")
        
        response = client.send(message, timeout=timeout)
        if response is not None:
            data, index, timestamp = decode_message(response)
            delay = (time.time_ns()-timestamp)/1e6

            print(f"Received response    index: {index:<6}    message: {len(response)} bytes    delay: {delay:<02.4f} ms")
        else:
            print("No response received")
        
        i += 1

        if sleep is not None:
            time.sleep(sleep)


def reply(
        address_client: str = "127.0.0.1",
        port_client: int = 5555,
        port_server: int = 5556,
        init: bool = False,
        number: int | None = 1000,
        size: int = 4048,
        sleep: float | None = 0.1
):
    if init:
        address_client = None
        port_client = None

    print("Reply server started")
    server = REP(
        address_client=address_client,
        port_client=port_client,
        port_server=port_server
    )

    if not server.connect(timeout=10000):
        print("Could not connect")

        return

    i = 0
    while number is None or i < number:
        message = server.recv()
        data, index, timestamp = decode_message(message)
        delay = (time.time_ns()-timestamp)/1e6
        print(f"Received message    index {index:<6}    message: {len(message)} bytes    delay: {delay:<02.4f} ms")

        response = generate_message(size=size, index=index)
        print(f"Sending response    index {index:<6}    message: {len(message)} bytes")
        server.resp(response)

        i += 1

        if sleep is not None:
            time.sleep(sleep)


@click.command()
@click.option(
    "-req", "--request", "mode",
    is_flag=True, flag_value="req",
    required=True
)
@click.option(
    "-rep", "--reply", "mode",
    is_flag=True, flag_value="rep",
    required=True
)
@click.option(
    "-ac", "--address_client",
    default="127.0.0.1",
    help="IP address of client"
)
@click.option(
    "-as", "--address_server",
    default="127.0.0.1",
    help="IP address of server"
)
@click.option(
    "-pc", "--port_client",
    type=int, default=5555,
    help="Port of client"
)
@click.option(
    "-ps", "--port_server",
    type=int, default=5556,
    help="Port of server"
)
@click.option(
    "-i", "--init",
    is_flag=True,
    help="Send/expect init message"
)
@click.option(
    "-t", "--timeout",
    default=1000,
    help="Time in ms to wait for incoming message"
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
        address_client: str = "127.0.0.1",
        address_server: str = "127.0.0.1",
        port_client: int = 5555,
        port_server: int = 5556,
        init: bool = False,
        timeout: int = 1000,
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
        case "req":
            request(
                address_client=address_client,
                address_server=address_server,
                port_client=port_client,
                port_server=port_server,
                init=init,
                timeout=timeout,
                number=number,
                size=size,
            )
        case "rep":
            reply(
                address_client=address_client,
                port_client=port_client,
                port_server=port_server,
                init=init,
                number=number,
                size=size
            )
        case _:
            print("Unknown command")


if __name__ == '__main__':
    main()

