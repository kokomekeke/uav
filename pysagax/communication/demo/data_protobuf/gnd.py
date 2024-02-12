import zmq
import enum

import data_pb2 as proto


class PacketType(enum.Enum):
    SPECTRUM = b"S"
    DETECTION = b"D"
    EVENT = b"E"
    TELEMETRY = b"T"


SERVER = "tcp://localhost:5563"

context = zmq.Context()

print("Connecting to UAV Server")
socket = context.socket(zmq.SUB)
socket.connect(SERVER)

# Subscribing to selected topics
socket.setsockopt(zmq.SUBSCRIBE, PacketType.SPECTRUM.value)
socket.setsockopt(zmq.SUBSCRIBE, PacketType.TELEMETRY.value)
#socket.setsockopt(zmq.SUBSCRIBE, PacketType.EVENT.value)
#socket.setsockopt(zmq.SUBSCRIBE, PacketType.DETECTION.value)

while True:
    # Receiving message
    [type, content] = socket.recv_multipart()

    # Decoding message
    match PacketType(type):
        case PacketType.SPECTRUM:
            data = proto.Spectrum()
            data.ParseFromString(content)
        case PacketType.DETECTION:
            data = proto.Detection()
            data.ParseFromString(content)
        case PacketType.EVENT:
            data = proto.Event()
            data.ParseFromString(content)
        case PacketType.TELEMETRY:
            data = proto.Telemetry()
            data.ParseFromString(content)
        case _:
            data = "Unknown packet type"

    # Displaying data
    print("====================")
    print(f"Packet type: {type.decode()}")
    print(f"Raw value: {content}")
    print(f"Message:")
    print(data)

socket.close()
context.term()