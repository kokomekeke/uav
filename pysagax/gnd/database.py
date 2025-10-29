import datetime
import enum
from typing import Any

from click.core import F
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class OperationMode(enum.Enum):
    MANUAL = 0
    SCANNING = 1
    TRACKING = 2


class UAVEntity(db.Model):
    __tablename__ = "uav"

    uav_id = db.Column(db.Integer(), primary_key=True)
    uav_label = db.Column(db.String(100))
    uav_address = db.Column(db.String(255))
    active = db.Column(db.Boolean(), nullable=False)
    conf_id = db.Column(
        db.Integer(), db.ForeignKey("configuration.conf_id"), nullable=True
    )
    last_seen = db.Column(db.DateTime(), default=datetime.datetime.now)
    last_pos_lat = db.Column(db.Numeric(10, 6))
    last_pos_lon = db.Column(db.Numeric(10, 6))
    last_pos_altitude = db.Column(db.Numeric(10, 3))
    last_pos_q0 = db.Column(db.Numeric(10, 6))
    last_pos_q1 = db.Column(db.Numeric(10, 6))
    last_pos_q2 = db.Column(db.Numeric(10, 6))
    last_pos_q3 = db.Column(db.Numeric(10, 6))
    health_report = db.Column(db.String(8191))


class UAVEventEntity(db.Model):
    """
    TODO: use or discard this table
    This should be a link table between uav and comintevent I guess
    """

    __tablename__ = "uav_event"
    uav_event_id = db.Column(db.Integer(), primary_key=True)
    uav_id = db.Column(db.Integer(), db.ForeignKey("uav.uav_id"), nullable=False)
    event_id = db.Column(
        db.Integer(), db.ForeignKey("comintevent.event_id"), nullable=False
    )
    avg_line_of_bearing_deg = db.Column(db.Numeric(6, 3))
    certainty_of_lob = db.Column(db.Numeric(4, 3))
    timestamp = db.Column(db.DateTime(), default=datetime.datetime.now, nullable=False)


class ComIntEventEntity(db.Model):
    """
    TODO: this could contain the final level of post-processing, such as trajectories aggregated from geolocations.
    """

    __tablename__ = "comintevent"

    event_id = db.Column(db.Integer(), primary_key=True)
    frequency = db.Column(db.BigInteger(), nullable=False)
    avg_signal_strength = db.Column(db.Numeric(8, 3))
    timestamp_of_first_detection = db.Column(
        db.DateTime(), default=datetime.datetime.now
    )
    duration_sec = db.Column(db.Numeric(10, 1))
    last_location_lat = db.Column(db.Numeric(10, 6))
    last_location_lon = db.Column(db.Numeric(10, 6))
    last_location_certainty_radius = db.Column(db.Numeric(10, 1))


class ComIntGeoLocEntity(db.Model):
    """
    Table for storing geolocation data calculated from ComInt detections.
    """

    __tablename__ = "comintgeoloc"

    geoloc_id = db.Column(db.BigInteger(), primary_key=True)  # autoincremented id

    # TODO: 2 detection_id columns if each row is triangulated from 2 meauserements or a link table
    # if a single geolocation is calculated from measurements of more than 2 uavs
    # TODO: also keep in mind, that detections from a single, but moving uav could be used for geolocating
    # detection_id = db.Column(db.Integer(), db.ForeignKey("comintdetection.detection_id"), nullable=False)

    # TODO:
    # uav_event_id = db.Column(
    #     db.Integer(), db.ForeignKey("uav_event.uav_event_id"), nullable=True
    # )

    roi_identifier = db.Column(db.Integer(), nullable=True)

    lat = db.Column(db.Numeric(10, 6))
    lon = db.Column(db.Numeric(10, 6))
    certainty_radius = db.Column(db.Numeric(10, 1))
    # Time difference between detections that produced this geolocation (seconds)
    detections_time_delta = db.Column(db.Interval)

    timestamp = db.Column(db.DateTime(), default=datetime.datetime.now, nullable=False)


class ComIntFilteredGeoLocEntity(db.Model):
    """
    Stores Kálmán filtered geolocation data calculated from ComInt detections.
    """

    __tablename__ = "comintfilteredgeoloc"

    geoloc_id = db.Column(db.BigInteger(), primary_key=True)  # autoincremented id


    roi_identifier = db.Column(db.Integer(), nullable=True)

    lat = db.Column(db.Numeric(10, 6))
    lon = db.Column(db.Numeric(10, 6))
    heading = db.Column(db.Numeric(10, 6))
    speed = db.Column(db.Numeric(10, 6))
    # certainty_radius = db.Column(db.Numeric(10, 1)

    timestamp = db.Column(db.DateTime(), default=datetime.datetime.now, nullable=False)


class ComIntDetectionEntity(db.Model):
    __tablename__ = "comintdetection"

    detection_id = db.Column(db.BigInteger(), primary_key=True)
    uav_id = db.Column(db.Integer(), db.ForeignKey("uav.uav_id"), nullable=False)
    uav_event_id = db.Column(
        db.Integer(), db.ForeignKey("uav_event.uav_event_id"), nullable=True
    )
    frequency = db.Column(db.BigInteger(), nullable=False)
    signal_strength = db.Column(db.Numeric(8, 3), nullable=False)
    bandwidth = db.Column(db.BigInteger(), nullable=False)
    snr = db.Column(db.Numeric(8, 3), nullable=False)
    lob_azim_deg = db.Column(db.Numeric(6, 3), nullable=False)
    lob_elev_deg = db.Column(db.Numeric(6, 3), nullable=False)
    precision = db.Column(db.Numeric(4, 3), nullable=False)
    timestamp = db.Column(db.DateTime(), default=datetime.datetime.now, nullable=False)
    uav_pos_lat = db.Column(db.Numeric(10, 6))
    uav_pos_lon = db.Column(db.Numeric(10, 6))
    uav_pos_altitude = db.Column(db.Numeric(10, 3))
    uav_pos_q0 = db.Column(db.Numeric(10, 6))
    uav_pos_q1 = db.Column(db.Numeric(10, 6))
    uav_pos_q2 = db.Column(db.Numeric(10, 6))
    uav_pos_q3 = db.Column(db.Numeric(10, 6))
    roi_identifier = db.Column(db.Integer(), nullable=True)


class ConfigurationEntity(db.Model):
    __tablename__ = "configuration"
    conf_id = db.Column(db.Integer(), primary_key=True)
    preset_name = db.Column(db.String(100), nullable=True)
    mode = db.Column(
        db.Enum(OperationMode), nullable=False, default=OperationMode.MANUAL
    )
    tracking_target = db.Column(
        db.Integer(), db.ForeignKey("comintevent.event_id"), nullable=True
    )


class AreaOfInterestEntity(db.Model):
    __tablename__ = "areaofinterest"
    aoi_id = db.Column(db.Integer(), primary_key=True)
    conf_id = db.Column(
        db.Integer(), db.ForeignKey("configuration.conf_id"), nullable=True
    )
    lat = db.Column(db.Numeric(10, 6))
    lon = db.Column(db.Numeric(10, 6))
    radius = db.Column(db.Numeric(10, 1))


class FreqOfInterestEntity(db.Model):
    __tablename__ = "freqofinterest"
    foi_id = db.Column(db.Integer(), primary_key=True)
    conf_id = db.Column(
        db.Integer(), db.ForeignKey("configuration.conf_id"), nullable=False
    )
    start_freq = db.Column(db.BigInteger(), nullable=False)
    end_freq = db.Column(db.BigInteger(), nullable=False)


class ComIntDatabase:

    def __init__(self, url) -> None:
        self.url = url

    def get_app_instance(self) -> Flask:
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = self.url
        db.init_app(app)
        return app

    def add(self, entity: Any) -> None:
        global db
        db.session.add(entity)

    def add_and_commit(self, entity: Any) -> None:
        global db
        db.session.add(entity)
        db.session.commit()

    def bulk_insert(self, entity_list: list[Any]):
        global db
        db.session.bulk_save_objects(entity_list)

    # TODO: do we need this?
    # def update(self, entity: Any) -> None:
    #     global db
    #     db.session.

    def commit(self) -> None:
        global db
        db.session.commit()

    def query(self, *args, **kwargs):
        global db
        return db.session.query(*args, **kwargs)

    def rollback(self) -> None:
        global db
        db.session.rollback()
        db.session.remove()

    def initialize_db(self, app) -> None:
        global db
        with app.app_context():
            db.create_all()
