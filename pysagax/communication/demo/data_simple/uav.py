import zmq
import enum
import random
import time


class PacketType(enum.Enum):
    SPECTRUM = b"S"
    DETECTION = b"D"
    EVENT = b"E"
    TELEMETRY = b"T"


ADDRESS = "tcp://*:5563"

context = zmq.Context()

print("Setting up UAV server")
socket = context.socket(zmq.PUB)
socket.bind(ADDRESS)

# Tracking sent package numbers
spectrum = 0
detection = 0
event = 0
telemetry = 0

while True:
    # Selecting packet type to send
    type = random.choice(list(PacketType))

    # Constructing appropriate message
    message = ""
    match type:
        case PacketType.SPECTRUM:
            message = f"Spectrum #{spectrum}"
            spectrum += 1
        case PacketType.DETECTION:
            message = f"Detection #{detection}"
            detection += 1
        case PacketType.EVENT:
            message = f"Event #{event}"
            event += 1
        case PacketType.TELEMETRY:
            message = f"Telemetry #{telemetry}"
            telemetry += 1
    
    # Displaying data
    print("====================")
    print(f"Sending [{type.value.decode()}] {message}")

    # Sending data
    socket.send_multipart([type.value, message.encode()])
    
    # Timeout
    time.sleep(0.1)
