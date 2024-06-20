import datetime
import enum
from click.core import F
from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    Numeric,
    BigInteger,
    Enum,
    ForeignKey,
)
from sqlalchemy.orm import relationship, backref

Base = declarative_base()


class OperationMode(enum.Enum):
    MANUAL = 0
    SCANNING = 1
    TRACKING = 2


class UAVEntity(Base):
    __tablename__ = "uav"

    uav_id = Column(Integer(), primary_key=True)
    uav_label = Column(String(100))
    uav_address = Column(String(255))
    active = Column(Boolean(), nullable=False)
    conf_id = Column(Integer(), ForeignKey("configuration.conf_id"), nullable=True)
    last_seen = Column(DateTime(), default=datetime.datetime.now)
    last_pos_lat = Column(Numeric(10, 6))
    last_pos_lon = Column(Numeric(10, 6))
    health_report = Column(String(255))


class UAVEventEntity(Base):
    __tablename__ = "uav_event"
    uav_event_id = Column(Integer(), primary_key=True)
    uav_id = Column(Integer(), ForeignKey("uav.uav_id"), nullable=False)
    event_id = Column(Integer(), ForeignKey("comintevent.event_id"), nullable=False)
    avg_line_of_bearing_deg = Column(Numeric(6, 3))
    certainty_of_lob = Column(Numeric(4, 3))
    timestamp = Column(DateTime(), default=datetime.datetime.now, nullable=False)


class ComIntEventEntity(Base):
    __tablename__ = "comintevent"

    event_id = Column(Integer(), primary_key=True)
    frequency = Column(BigInteger(), nullable=False)
    avg_signal_strength = Column(Numeric(8, 3))
    timestamp_of_first_detection = Column(DateTime(), default=datetime.datetime.now)
    duration_sec = Column(Numeric(10, 1))
    last_location_lat = Column(Numeric(10, 6))
    last_location_lon = Column(Numeric(10, 6))
    last_location_certainty_radius = Column(Numeric(10, 1))


class ComIntDetectionEntity(Base):
    __tablename__ = "comintdetection"

    detection_id = Column(Integer(), primary_key=True)
    uav_id = Column(Integer(), ForeignKey("uav.uav_id"), nullable=False)
    uav_event_id = Column(
        Integer(), ForeignKey("uav_event.uav_event_id"), nullable=True
    )
    frequency = Column(BigInteger(), nullable=False)
    signal_strength = Column(Numeric(8, 3), nullable=False)
    bandwidth = Column(BigInteger(), nullable=False)
    snr = Column(Numeric(8, 3), nullable=False)
    lob_azim_deg = Column(Numeric(6, 3), nullable=False)
    lob_elev_deg = Column(Numeric(6, 3), nullable=False)
    precision = Column(Numeric(4, 3), nullable=False)
    timestamp = Column(DateTime(), default=datetime.datetime.now, nullable=False)


class ConfigurationEntity(Base):
    __tablename__ = "configuration"
    conf_id = Column(Integer(), primary_key=True)
    preset_name = Column(String(100), nullable=True)
    mode = Column(Enum(OperationMode), nullable=False, default=OperationMode.MANUAL)
    tracking_target = Column(
        Integer(), ForeignKey("comintevent.event_id"), nullable=True
    )


class AreaOfInterest(Base):
    __tablename__ = "areaofinterest"

    foi_id = Column(Integer(), primary_key=True)
    conf_id = Column(Integer(), ForeignKey("configuration.conf_id"), nullable=False)
    start_freq = Column(BigInteger(), nullable=False)
    end_freq = Column(BigInteger(), nullable=False)


class FreqOfInterest(Base):
    __tablename__ = "freqofinterest"

    aoi_id = Column(Integer(), primary_key=True)
    conf_id = Column(Integer(), ForeignKey("configuration.conf_id"), nullable=True)
    lat = Column(Numeric(10, 6))
    lon = Column(Numeric(10, 6))
    radius = Column(Numeric(10, 1))


class ComIntDatabase:

    def __init__(self, url) -> None:
        self._engine = create_engine(url)
        self._connection = self._engine.connect()
        pass

    def initialize_db(self) -> None:
        global Base
        Base.metadata.create_all(self._engine)  # type: ignore
