import zmq
import enum
import random
import time

import data_pb2 as proto


class PacketType(enum.Enum):
    SPECTRUM = b"S"
    DETECTION = b"D"
    EVENT = b"E"
    TELEMETRY = b"T"


STREAM_ID = 42
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
    match type:
        case PacketType.SPECTRUM:
            data = proto.Spectrum()
            data.time.GetCurrentTime()
            data.stream_id = STREAM_ID
            for i in range(random.randint(0, 4)):
                # 'repeated' fields cannot be assigned, only appended
                data.magnitude.append(random.random()*256)
            spectrum += 1
        case PacketType.DETECTION:
            data = proto.Detection()
            data.time.GetCurrentTime()
            data.stream_id = STREAM_ID
            data.level = random.random()*256
            detection += 1
        case PacketType.EVENT:
            data = proto.Event()
            data.time.GetCurrentTime()
            data.stream_id = STREAM_ID
            event += 1
        case PacketType.TELEMETRY:
            data = proto.Telemetry()
            data.time.GetCurrentTime()
            data.stream_id = STREAM_ID
            data.disc_usage = random.randint(0, 64000000000)
            telemetry += 1
    
    # Displaying data
    print("====================")
    print(f"Sending packet type {type.value.decode()}")
    print(f"Message:")
    print(data)

    # Sending data
    socket.send_multipart([type.value, data.SerializeToString()])
    
    # Timeout
    time.sleep(1)
