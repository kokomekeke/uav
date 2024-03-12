import time
import zmq
import random

QUERIES = [b"QUERY"]

context = zmq.Context()

print("Setting up UAV server")
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

while True:
    print("==========")

    print("Waiting for command")
    command = socket.recv()

    print(f"Received command \"{command.decode()}\"")

    if command in QUERIES:
        print(f"Sending response DATA")
        socket.send(b"DATA")
    else:
        time.sleep(random.randint(1, 5))

        print(f"Sending response ACK")
        socket.send(b"ACK")