import flask
from flask import jsonify, make_response
from sqlalchemy.sql import text
from flask_marshmallow_openapi import open_api

from pysagax.gnd.api.api_utils import geojson_feature_from_detection, geojson_feature_from_uav, geojson_feature_from_geoloc
from pysagax.gnd.api.model import ComIntDetectionSchema, ComIntEventSchema, UAVSchema, UAVCreateSchema, UAVUpdateSchema, GeoJSONSchema
from pysagax.gnd.database import (
    ComIntDetectionEntity,
    UAVEntity,
    ComIntGeoLocEntity,
    db,
)

api = flask.Blueprint("api", __name__)

comintdetections_schema = ComIntDetectionSchema(many=True)
comintdetection_schema = ComIntDetectionSchema()

comintevent_schema = ComIntEventSchema()

uavs_schema = UAVSchema(many=True)
uav_schema = UAVSchema()


def not_found_error(message):
    return make_response(jsonify(message), 404)


@open_api.get(response_schema=ComIntDetectionSchema, is_list=True, has_id_in_path=True)
@api.route("/comintdetection/list_from/<int:id>", methods=["GET"])
def comintdetection_list(id):
    all_detections = (
        ComIntDetectionEntity.query.order_by(ComIntDetectionEntity.detection_id.desc())
        .filter(ComIntDetectionEntity.detection_id >= id)
        .all()
    )
    return jsonify(comintdetections_schema.dump(all_detections))


@open_api.get(
    response_schema=GeoJSONSchema,
    has_id_in_path=True,
)
@api.route("/comintdetection/geojson/list_from/<int:id>", methods=["GET"])
def comintdetection_geojson_list(id):
    all_detections = (
        ComIntDetectionEntity.query.order_by(ComIntDetectionEntity.detection_id.asc())
        .filter(ComIntDetectionEntity.detection_id >= id)
        .all()
    )
    return jsonify(
        {
            "type": "FeatureCollection",
            "name": "ComIntDetection",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
            },
            "features": [geojson_feature_from_detection(det) for det in all_detections],
        }
    )


@open_api.get(
    response_schema=GeoJSONSchema,
    has_id_in_path=True,
)
@api.route("/comintdetection/geojson/list_last/<int:limit>", methods=["GET"])
def comintdetection_geojson_list_last(limit):
    """
    Return a geojson of the most recent detections.
    limit sets the number of returned detections.
    uav URL parameter filters the detections for the given uav_ids.
    roi URL parameter filters the detections for the given roi_ids.
    if stride URL parameter is specifie:d it only returns every n-th row of the detection DB.

    Usage with limit=1000, uav=[10, 12, 15] and stride=5
        .../geojson/list_last/1000?uav=10@&uav=12&uav=15&stride=5

    """
    stride = flask.request.args.get("stride", 1, type=int)
    uavs = flask.request.args.getlist("uav", type=int)
    roi_ids = flask.request.args.getlist("roi_id", type=int)
    event_ids = flask.request.args.getlist("e_id", type=int)
    # freqs = flask.request.args.getlist("freq", type=int)

    # sql = """
    # WITH ranked AS (
    #     SELECT *,
    #         ROW_NUMBER() OVER (ORDER BY detection_id DESC) AS rn
    #     FROM comintdetection
    #     {where_clause}
    # )
    # SELECT *
    # FROM ranked
    # WHERE (rn - 1) % :stride = 0
    # ORDER BY detection_id DESC
    # LIMIT :limit
    # """
    sql = """
    WITH ranked AS (
        SELECT *
        FROM comintdetection
        {where_clause}
    )
    SELECT *
    FROM ranked
    WHERE detection_id % :stride = 0 
    ORDER BY detection_id DESC
    LIMIT :limit
    """

    # where_clause = "WHERE uav_id IN :uavs" if uavs else ""  # filter if uav_id is given

    # where_clause = f"WHERE uav_id IN {':uavs' if uavs else '*'} AND roi_identifier IN {':roi_ids' if roi_ids else '*'} AND event_id IN {':event_id' if event_ids else '*'}"

    # uavs = uavs if uavs else "*"
    # roi_ids = roi_ids if roi_ids else "*"
    # event_ids = event_ids if event_ids else "*"
    # where_clause = f"WHERE uav_id IN :uavs AND roi_identifier IN :roi_ids AND event_id IN :event_ids"

    where_clause_parts = []
    where_clause_parts.append("uav_id IN :uavs" if uavs else "")
    where_clause_parts.append("roi_identifier IN :roi_ids" if roi_ids else "")
    where_clause_parts.append("event_id IN :event_id" if event_ids else "")

    where_clause = " AND ".join(filter(None, where_clause_parts))
    where_clause = "WHERE " + where_clause if where_clause else ""


    sql = sql.format(where_clause=where_clause)
    query = db.session.query(ComIntDetectionEntity).from_statement(text(sql))

    params = {"stride": stride, "limit": limit}
    if uavs: params["uavs"] = tuple(uavs)
    if roi_ids: params["roi_ids"] = tuple(roi_ids)
    if event_ids: params["event_ids"] = tuple(event_ids)

    detections = query.params(**params).all()

    return jsonify(
        {
            "type": "FeatureCollection",
            "name": "ComIntDetection",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
            },
            "features": [geojson_feature_from_detection(det) for det in detections],
        }
    )


@open_api.get_detail(ComIntDetectionSchema)
@api.route("/comintdetection/<int:id>", methods=["GET"])
def comintdetection_detail(id):
    comintdetection = ComIntDetectionEntity.query.get(id)
    return comintdetection_schema.jsonify(comintdetection)


@open_api.get(
    response_schema=GeoJSONSchema,
    has_id_in_path=True,
)
@api.route("/comintgeoloc/geojson/list_last/<int:limit>", methods=["GET"])
def comintevent_geojson(limit):
    """
    Return a geojson of the most recent geolocations.
    limit sets the number of returned points.
    roi URL parameter filters the points for the given roi_ids.
    if stride URL parameter is specified it only returns every n-th row of the geolocation table.

    Usage with limit=1000, roi=[10, 12, 15] and stride=5
        .../geojson/list_last/1000?roi=10@&roi=12&roi=15&stride=5

    """
    stride = flask.request.args.get("stride", 1, type=int)
    roi_ids = flask.request.args.getlist("roi_id", type=int)

    sql = """
    WITH ranked AS (
        SELECT *
        FROM comintgeoloc
        {where_clause}
    )
    SELECT *
    FROM ranked
    WHERE geoloc_id % :stride = 0 
    ORDER BY geoloc_id DESC
    LIMIT :limit
    """

    where_clause = "WHERE roi_identifier IN :roi_ids" if roi_ids else ""

    sql = sql.format(where_clause=where_clause)
    query = db.session.query(ComIntGeoLocEntity).from_statement(text(sql))

    params = {"stride": stride, "limit": limit}
    if roi_ids:
        params["roi_ids"] = tuple(roi_ids)

    points = query.params(**params).all()

    return jsonify(
        {
            "type": "FeatureCollection",
            "name": "ComIntGeoLoc",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
            },
            "features": [geojson_feature_from_geoloc(point) for point in points],
        }
    )


@open_api.get_list(UAVSchema)
@api.route("/uav/")
def uav_list():
    all_uavs = UAVEntity.query.order_by(UAVEntity.uav_id.asc()).all()
    return jsonify(uavs_schema.dump(all_uavs))


@open_api.get(
    response_schema=GeoJSONSchema,
    has_id_in_path=False,
)
@api.route("/uav/geojson", methods=["GET"])
def uav_geojson_list():
    all_uavs = UAVEntity.query.order_by(UAVEntity.uav_id.asc()).all()
    return jsonify(
        {
            "type": "FeatureCollection",
            "name": "UAV",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
            },
            "features": [geojson_feature_from_uav(uav) for uav in all_uavs],
        }
    )


@open_api.get_detail(UAVSchema)
@api.route("/uav/<int:id>", methods=["GET"])
def uav_detail(id):
    uav = UAVEntity.query.get(id)
    if uav is None:
        return not_found_error(f"UAV {id} not found.")
    return uav_schema.jsonify(uav)


@open_api.post(request_schema=UAVCreateSchema, response_schema=UAVSchema)
@api.route("/uav", methods=["POST"])
def uav_create():
    data = UAVCreateSchema(many=False).load(flask.request.json)
    new_uav = UAVEntity()
    new_uav.active = data["active"]
    new_uav.uav_label = data["uav_label"]
    new_uav.uav_address = data["uav_address"]
    db.session.add(new_uav)
    db.session.commit()
    return uav_schema.jsonify(new_uav)


@open_api.patch(request_schema=UAVUpdateSchema, response_schema=UAVSchema)
@api.route("/uav/<int:id>", methods=["PATCH"])
def uav_update(id):
    data = UAVUpdateSchema(many=False).load(flask.request.json)
    uav = UAVEntity.query.get(id)
    if uav is None:
        return not_found_error(f"UAV {id} not found.")
    if "active" in data:
        uav.active = data["active"]
    if "uav_label" in data:
        uav.uav_label = data["uav_label"]
    if "uav_address" in data:
        uav.uav_address = data["uav_address"]
    db.session.commit()
    return uav_schema.jsonify(uav)


@open_api.delete(UAVSchema)
@api.route("/uav/<int:id>", methods=["DELETE"])
def uav_delete(id):
    uav = UAVEntity.query.get(id)
    if uav is None:
        return not_found_error(f"UAV {id} not found.")
    db.session.delete(uav)
    db.session.commit()
    return jsonify({})

