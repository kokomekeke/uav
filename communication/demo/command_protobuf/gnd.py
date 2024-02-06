import zmq
import random

import command_pb2 as proto

TIMEOUT_MS = 4000
SERVER = "tcp://localhost:5555"
INSTRUCTIONS = [
    proto.QUERY,
    proto.START,
    proto.STOP,
    proto.REC
]

context = zmq.Context()

print("Connecting to UAV server")
socket = context.socket(zmq.REQ)
socket.connect(SERVER)

while True:
    print("==========")

    # Constructing command
    command = proto.Command()
    command.type = random.choice(INSTRUCTIONS)
    match command.type:
        case proto.START:
            command.start_id = random.randint(1, 3)
        case proto.STOP:
            command.stop_id = random.randint(1, 3)

    while True:
        print(f"Sending command {command.type}:")
        print(command)
        socket.send(command.SerializeToString())
            
        print(f"Waiting for response")
        if(socket.poll(TIMEOUT_MS) & zmq.POLLIN) != 0:
            reply = socket.recv()
            response = proto.Response()
            response.ParseFromString(reply)

            print(f"Received reply")
            print(f"Raw: {reply}")
            print(f"Decoded:")
            print(response)
            break
        else:
            print("No response from UAV server, reconnecting")

            socket.setsockopt(zmq.LINGER, 0)
            socket.close()

            socket = context.socket(zmq.REQ)
            socket.connect(SERVER)
