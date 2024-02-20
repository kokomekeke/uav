from enum import Enum

from pysagax.message.data_pb2 import Telemetry, Measurement, Event, OperationalError

class DataType(Enum):
    TELEMETRY = "t"
    MEASUREMENT = "m"
    EVENT = "v"
    ERROR = "e"

    def to_message(self) -> Telemetry | Measurement | Event | OperationalError:
        """Returns an empty Protobuf Message of the corresponding type"""

        match self:
            case self.TELEMETRY:
                return Telemetry()
            case self.MEASUREMENT:
                return Measurement()
            case self.EVENT:
                return Event()
            case self.ERROR:
                return OperationalError()

    @classmethod
    def from_message(cls,
            message: Telemetry | Measurement | Event | OperationalError
    ) -> "DataType":
        """Returns corresponding ENUM value based on Protobuf Message type"""

        match message:
            case Telemetry():
                return cls.TELEMETRY
            case Measurement():
                return cls.MEASUREMENT
            case Event():
                return cls.EVENT
            case OperationalError():
                return cls.MEASUREMENT
