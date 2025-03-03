from pysagax.gnd.database import UAVEntity, ComIntDetectionEntity
from pysagax.util.mat import yaw_pitch_roll_from_quaternion


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
