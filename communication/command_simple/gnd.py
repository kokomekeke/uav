import zmq
import random

TIMEOUT_MS = 4000
SERVER = "tcp://localhost:5555"
COMMANDS = [b"START", b"STOP", b"REC", b"QUERY"]

context = zmq.Context()

print("Connecting to UAV server")
socket = context.socket(zmq.REQ)
socket.connect(SERVER)

while True:
    print("==========")

    command = random.choice(COMMANDS)

    while True:
        print(f"Sending command {command.decode()}")
        socket.send(command)
            
        print(f"Waiting for response")
        if(socket.poll(TIMEOUT_MS) & zmq.POLLIN) != 0:
            reply = socket.recv()

            print(f"Received reply \"{reply.decode()}\"")
            break
        else:
            print("No response from UAV server, reconnecting")

            socket.setsockopt(zmq.LINGER, 0)
            socket.close()

            socket = context.socket(zmq.REQ)
            socket.connect(SERVER)
