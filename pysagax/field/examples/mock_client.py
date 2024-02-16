#!/usr/bin/env python3
import random

#TODO: Fix imports with proper package structure
import sys, os
#sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import pysagax.message.command_pb2 as proto
from communication.req import REQ


instructions = [
    proto.PING,
    proto.CONFIG,
    proto.POSITION,
]


client = REQ()
client.connect()

id = 1
while True:
    print("==========")

    instruction = random.choice(instructions)

    command = proto.Command()
    command.id = id
    command.instruction = instruction

    match instruction:
        case proto.PING:
            command.ping_data = "PING"
        case proto.POSITION:
            if random.choice((True, False)):
                command.position = 42
    
    print("Command:")
    print(command, end="")
    raw_response = client.send(command.SerializeToString())

    if raw_response is not None:
        response = proto.Response()
        response.ParseFromString(raw_response)

        print("Response:")
        print(response, end="")
    
    else:
        print("No response")
    
    id += 1
