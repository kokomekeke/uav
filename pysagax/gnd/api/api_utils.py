from pysagax.gnd.database import UAVEntity, ComIntDetectionEntity, ComIntGeoLocEntity
from pysagax.util.mat import yaw_pitch_roll_from_quaternion

import pysagax.message.command_pb2 as proto_cmd
import queue

from math import isfinite

queue_to_command_engine = None
queue_from_command_engine = None

def _set_queues(to_command_enginge, from_command_engine):
    """Used by pysagax_gnd_api.py to pass queue object to this file"""
    global queue_to_command_engine, queue_from_command_engine
    queue_to_command_engine = to_command_enginge
    queue_from_command_engine = from_command_engine

def geojson_feature_from_uav(
    uav: UAVEntity,
) -> dict[str, str | dict[str, int | float | str | list[float]]]:
    if all(
        q is not None
        for q in [uav.last_pos_q0, uav.last_pos_q1, uav.last_pos_q2, uav.last_pos_q3]
    ):
        try:
            yaw, pitch, roll = yaw_pitch_roll_from_quaternion(
                [
                    float(uav.last_pos_q0),
                    float(uav.last_pos_q1),
                    float(uav.last_pos_q2),
                    float(uav.last_pos_q3),
                ]
            )
        except:
            yaw, pitch, roll = 0.0, 0.0, 0.0
    else:
        yaw, pitch, roll = 0.0, 0.0, 0.0
    return {
        "type": "Feature",
        "properties": {
            "uav_id": uav.uav_id,
            "uav_label": uav.uav_label,
            "active": bool(uav.active),
            "conf_id": uav.conf_id,
            "last_seen": str(uav.last_seen.isoformat("T")),
            "last_pos_altitude": float(uav.last_pos_altitude),
            "last_pos_yaw": yaw,
            "last_pos_pitch": pitch,
            "last_pos_roll": roll,
            "health_report": uav.health_report,
        },
        "geometry": {
            "type": "Point",
            "coordinates": [float(uav.last_pos_lon), float(uav.last_pos_lat)],
        },
    }


def geojson_feature_from_detection(
    det: ComIntDetectionEntity,
) -> dict[str, str | dict[str, int | float | str | list[float]]]:
    if all(
        q is not None
        for q in [det.uav_pos_q0, det.uav_pos_q1, det.uav_pos_q2, det.uav_pos_q3]
    ):
        try:
            yaw, pitch, roll = yaw_pitch_roll_from_quaternion(
                [
                    float(det.uav_pos_q0),
                    float(det.uav_pos_q1),
                    float(det.uav_pos_q2),
                    float(det.uav_pos_q3),
                ]
            )
        except:
            yaw, pitch, roll = 0.0, 0.0, 0.0
    else:
        yaw, pitch, roll = 0.0, 0.0, 0.0
    return {
        "type": "Feature",
        "properties": {
            "bandwidth": float(det.bandwidth),
            "detection_id": det.detection_id,
            "frequency": int(det.frequency),
            "lob_azim_deg": float(det.lob_azim_deg),
            "lob_elev_deg": float(det.lob_elev_deg),
            "precision": float(det.precision),
            "signal_strength": float(det.signal_strength),
            "snr": float(det.snr),
            "timestamp": str(det.timestamp.isoformat("T")),
            "uav_event_id": det.uav_event_id,
            "uav_id": det.uav_id,
            "uav_pos_altitude": float(det.uav_pos_altitude),
            "uav_pos_yaw": yaw,
            "uav_pos_pitch": pitch,
            "uav_pos_roll": roll,
            "roi_id": det.roi_identifier,
        },
        "geometry": {
            "type": "Point",
            "coordinates": [float(det.uav_pos_lon), float(det.uav_pos_lat)],
        },
    }


def geojson_feature_from_geoloc(
    point: ComIntGeoLocEntity,
) -> dict[str, str | dict[str, int | float | str | list[float]]]:
    # TODO: WHY do we save NaN values to the DB? do we want that? It might be useful to keep track of the unsuccessful geolocation attempts.
    lat = float(point.lat)
    lon = float(point.lon)
    if not (isfinite(lat) and isfinite(lon)):
        # json standard doesn't have NaN and QGIS can't handle these values 
        lat, lon = (0.0, 0.0)
    return {
        "type": "Feature",
        "properties": {
            "geoloc_id": point.geoloc_id,
            "certainty_radius": point.certainty_radius,
            "roi_id": point.roi_identifier,
            "detections_time_delta": point.detections_time_delta.total_seconds(),
            "timestamp": str(point.timestamp.isoformat("T")),
        },
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
    }

def send_to_command_engine(target_id: int, cmd: proto_cmd.Command) -> proto_cmd.Response:
    queue_to_command_engine.put((target_id, cmd))
    try:
        response = queue_from_command_engine.get(timeout=1)
    except queue.Empty:
        print ("No response from CommAggregate")
        response = proto_cmd.Response(error=proto_cmd.CommandError(description="no answer:("))
        # TODO: raise valami találó exception response helyett

    return response
    
    