import zmq
import enum


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

    # Displaying data
    print("====================")
    print(f"[{type.decode()}] {content.decode()}")

socket.close()
context.term()