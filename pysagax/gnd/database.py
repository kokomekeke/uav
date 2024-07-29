import datetime
import enum

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
    health_report = db.Column(db.String(255))


class UAVEventEntity(db.Model):
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


class ComIntDetectionEntity(db.Model):
    __tablename__ = "comintdetection"

    detection_id = db.Column(db.Integer(), primary_key=True)
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

    foi_id = db.Column(db.Integer(), primary_key=True)
    conf_id = db.Column(
        db.Integer(), db.ForeignKey("configuration.conf_id"), nullable=False
    )
    start_freq = db.Column(db.BigInteger(), nullable=False)
    end_freq = db.Column(db.BigInteger(), nullable=False)


class FreqOfInterestEntity(db.Model):
    __tablename__ = "freqofinterest"

    aoi_id = db.Column(db.Integer(), primary_key=True)
    conf_id = db.Column(
        db.Integer(), db.ForeignKey("configuration.conf_id"), nullable=True
    )
    lat = db.Column(db.Numeric(10, 6))
    lon = db.Column(db.Numeric(10, 6))
    radius = db.Column(db.Numeric(10, 1))


class ComIntDatabase:

    def __init__(self, url) -> None:
        self.url = url

    def get_app_instance(self) -> Flask:
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = self.url
        db.init_app(app)
        return app

    def initialize_db(self, app) -> None:
        global db
        with app.app_context():
            db.create_all()
