import time
import zmq
import random

import command_pb2 as proto

# Setting up mock processes
process_one = False
process_two = False

# Setting up ZeroMQ
context = zmq.Context()

print("Setting up UAV server")
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

while True:
    print("==========")

    print("Waiting for command")
    message = socket.recv()
    command = proto.Command()
    command.ParseFromString(message)

    print(f"Received command")
    print(f"Raw value: {message}")
    print(f"Decoded packet:")
    print(command)

    # Executing command and constructing response
    response = proto.Response()
    response.type = command.type
    match command.type:
        case proto.START:
            # Starting processes
            match command.start_id:
                case 1:
                    process_one = True
                case 2:
                    process_two = True
                case _:
                    #response.error = proto.Response.ResponseError()
                    response.error.description = "No such process"
        case proto.STOP:
            # Stopping processes
            match command.stop_id:
                case 1:
                    process_one = False
                case 2:
                    process_two = False
                case _:
                    #response.error = proto.Response.ResponseError()
                    response.error.description = "No such process"
        case proto.QUERY:
            # Constructing data from current status
            response.query_data = "Process #1: {} | Process #2: {}".format(
                "Running" if process_one else "Stopped",
                "Running" if process_two else "Stopped"
            )

    # Sending response
    socket.send(response.SerializeToString())

    time.sleep(1)
