from enum import Enum

from pysagax.message.data_pb2 import Telemetry, Measurement, Event, OperationalError

class DataType(Enum):
    TELEMETRY = "t"
    MEASUREMENT = "m"
    EVENT = "v"
    ERROR = "e"

    @classmethod
    def from_message(cls,
            message: Telemetry | Measurement | Event | OperationalError
    ) -> "DataType":
        match message:
            case Telemetry():
                return cls.TELEMETRY
            case Measurement():
                return cls.MEASUREMENT
            case Event():
                return cls.EVENT
            case OperationalError():
                return cls.MEASUREMENT
