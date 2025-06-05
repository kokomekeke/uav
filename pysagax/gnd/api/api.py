import logging
# TODO: felváltható e JSONIFY-al?
import json
import time

import flask
from flask import jsonify, make_response, current_app, Response, request, stream_with_context
from sqlalchemy.sql import text
from flask_marshmallow_openapi import open_api


import pysagax.message.command_pb2 as proto_cmd
from google.protobuf.json_format import Parse, MessageToDict, ParseDict

from pysagax.gnd.api.api_utils import (
    geojson_feature_from_detection,
    geojson_feature_from_uav,
    geojson_feature_from_geoloc,
    send_to_command_engine,
)
from pysagax.gnd.api.model import (
    ComIntDetectionSchema,
    ComIntEventSchema,
    UAVSchema,
    UAVCreateSchema,
    UAVUpdateSchema,
    GeoJSONSchema,
)
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

logger = logging.getLogger("api")


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
    if uavs:
        params["uavs"] = tuple(uavs)
    if roi_ids:
        params["roi_ids"] = tuple(roi_ids)
    if event_ids:
        params["event_ids"] = tuple(event_ids)

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


# mapping of command instructions to parameter name and message type tuples
# if no parameter is used for the instruction, the value is None
INSTRUCTION_MAP = {
    proto_cmd.Instruction.PING: ("ping_data", str),
    proto_cmd.Instruction.CONFIG: ("config", proto_cmd.Config),
    proto_cmd.Instruction.TELEMETRY: None,
    proto_cmd.Instruction.INFO: None,
    proto_cmd.Instruction.CONFIG_STATUS: None,
    proto_cmd.Instruction.PY_RESET: None,
    proto_cmd.Instruction.CS_START: None,
    proto_cmd.Instruction.CS_STOP: None,
    proto_cmd.Instruction.CS_RESTART: None,
    proto_cmd.Instruction.CS_PING: ("ping_data", str),
    proto_cmd.Instruction.SOURCE_START: None,
    proto_cmd.Instruction.SOURCE_STOP: None,
    proto_cmd.Instruction.POSITION: ("position", int),
    proto_cmd.Instruction.REC_START: None,
    proto_cmd.Instruction.REC_STOP: None,
    proto_cmd.Instruction.HEADING_START: None,
    proto_cmd.Instruction.HEADING_STOP: None,
    proto_cmd.Instruction.HEADING_RESTART: None,
    proto_cmd.Instruction.STREAM_START: ("target", proto_cmd.StreamTarget),
    proto_cmd.Instruction.STREAM_STOP: ("target", proto_cmd.StreamTarget),
    proto_cmd.Instruction.SELF_TEST: None,
    proto_cmd.Instruction.CS_SCAN_START: None,
    proto_cmd.Instruction.CS_CALIBRATE_START: (
        "calib_command",
        proto_cmd.CalibrationCommand,
    ),
    proto_cmd.Instruction.CS_CALIBRATE_ABORT: None,
    proto_cmd.Instruction.CS_TURN_OFF_COMPENSATION: None,
    proto_cmd.Instruction.CS_TURN_ON_COMPENSATION: None,
    proto_cmd.Instruction.CS_READ_PHASEDIFFS_FROM_FILE: (
        "calib_command",
        proto_cmd.CalibrationCommand,
    ),
    proto_cmd.Instruction.CS_CALIBRATION_VALUES_QUERY: None,
    proto_cmd.Instruction.CS_CALIBRATION_PHASE_CHECK: None,
    proto_cmd.Instruction.AUTO_CALIBRATION_ENABLE: None,
    proto_cmd.Instruction.AUTO_CALIBRATION_DISABLE: None,
    proto_cmd.Instruction.AUTO_CALIBRATION_TRIGGER: None,
    proto_cmd.Instruction.CS_RELOAD_CONFIG: None,
    proto_cmd.Instruction.FORWARD_TO_APM: ("msg_to_apm", proto_cmd.MessageToAPM),
}
cmd_id = 0


@api.route("/uav/<int:id>/command/<string:instruction>/", methods=["POST"])
def command(id, instruction):
    """
    Dynamically handle different types of commands based on the URL.

    The HTTP/POST request should define the command's instruction in the URL.
    The body of the request should have content-type 'application/json' and contain
    the parameter of the corresponding protobuf Command.
    Eg.
        instruction == 'ping' -> body:string
        instruction == 'config' -> body:json representation of Config protobuf message.
    """

    def assign_command_parameter(cmd, parameter_name, parameter):
        """Fills in the oneof parameter field in the command message"""
        try:
            # For parameter fields with default types (eg ping_data)
            setattr(cmd, parameter_name, parameter)
        except AttributeError:
            # For parameter fields of protobuf messages (eg config, target)
            getattr(cmd, parameter_name).CopyFrom(parameter)

    def convert_parameter_from_json_to_protobuf(parameter_type, raw_data):
        """
        Converting the body of HTTP POST request containing the parameter
        to the type the Command packet expects based on the instruction string.
        """
        try:
            # For parameter fields of protobuf messages (eg config, target)
            parameter = parameter_type()  # create the correct message object
            ParseDict(raw_data, parameter, ignore_unknown_fields=True)  # fill from json
            # TODO: Maybe set ignore_unknown_fields=False and warn if
            #       provided JSON is not compatible with protobuf definition
        except AttributeError:
            # For parameter fields with default types (eg ping_data)
            parameter = raw_data
        return parameter

    try:
        # convert instruction from URL to protobuf enum
        instruction_enum_value = proto_cmd.Instruction.Value(instruction.upper())
    except ValueError:
        emsg = f"Invalid instruction ('{instruction.upper()}') specified in the URL"
        logger.error(f"COMMAND: {emsg}")
        return jsonify({"error": emsg}), 400
    # Check instruction
    if instruction_enum_value not in INSTRUCTION_MAP.keys():
        emsg = f"Instruction ('{instruction.upper()}') is not yet supported"
        logger.error(f"COMMAND: {emsg}")
        return jsonify({"error": emsg}), 400

    # Parse incoming JSON data into the corresponding Protobuf message
    if flask.request.is_json:
        raw_data = flask.request.get_json()
    else:
        raw_data = b""

    logger.trace(f"Command endpoint: \n\tINSTRUCTION={instruction}\n\tDATA={raw_data}")

    # create the Command packet that'll contain the instruction and the parameter
    cmd = proto_cmd.Command()

    if INSTRUCTION_MAP[instruction_enum_value] is not None:
        # If the instruction expects a parameter -> fill it
        # Get parameter type name corresponding to the specified instruction
        parameter_name = INSTRUCTION_MAP[instruction_enum_value][0]
        parameter_type = INSTRUCTION_MAP[instruction_enum_value][1]

        parameter = convert_parameter_from_json_to_protobuf(parameter_type, raw_data)

        # Fill in the oneof parameter field
        assign_command_parameter(cmd, parameter_name, parameter)

    # Fill in instruction
    cmd.instruction = instruction_enum_value

    # TODO: fill cmd.id
    global cmd_id
    cmd.id = cmd_id
    cmd_id += 1

    response: proto_cmd.Response = send_to_command_engine(target_id=id, cmd=cmd)
    # TODO: check response.id == cmd.id??
    #       or each module that needs a cmd and rsp queue should have separate
    #       queues with maxsize=1, and CommAggregate should handle them all separately

    # Convert Protobuf message back to JSON for response
    return jsonify(MessageToDict(response))

@api.route("/stream/comint_detection", methods=["GET", "OPTIONS"])
def comint_detection_stream():
    if request.method == 'OPTIONS':
        return Response('', status=204, headers={
            "Access-Control-Allow-Origin": "http://localhost:5173",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Credentials": "true"
        })

    if not hasattr(current_app, 'measurement_to_stream_queue'):
        return make_response(jsonify({"error": "Stream queue not available"}), 503)

    app_queue = current_app.measurement_to_stream_queue
    app_logger = current_app.logger

    default_batch_interval = 0.2
    min_batch_interval = 0.01
    max_batch_interval = 2.0
    max_connection_time = 3600

    try:
        requested_interval = request.args.get('interval', default_batch_interval, type=float)
        batch_interval = max(min_batch_interval, min(requested_interval, max_batch_interval))
        # with current_app.app_context():
        current_app.batch_interval = batch_interval
    except ValueError:
        batch_interval = default_batch_interval
        app_logger.warning(f"Invalid interval parameter, using default: {default_batch_interval}")

    def generate():
        start_time = time.perf_counter()
        last_sent_time = start_time
        try:
            while True:
                current_time = time.perf_counter()
                if current_time - start_time >= max_connection_time:
                    app_logger.info("Max connection time reached")
                    yield f"data: {json.dumps({'info': 'Connection timeout reached'})}\n\n"
                    break
                if current_time - last_sent_time >= batch_interval and not app_queue.empty():
                    print("NOT EMPTY")
                    data = app_queue.get(block=False)
                    yield f"data: {json.dumps(data)}\n\n"
                    # print("Stream", end=" ")
                    last_sent_time = current_time
                else:
                    print("QUEUE IS EMPTY")
                time.sleep(0.05)
                print("Queue size:", app_queue.qsize())
        except GeneratorExit:
            app_logger.info("Client disconnected from stream")
        except Exception as e:
            app_logger.error(f"Error in stream: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    app_logger.info(
        f"Starting comint_detection stream with interval: {batch_interval}s, max time: {max_connection_time}s")

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "http://localhost:5173",
            "Access-Control-Allow-Credentials": "true",
        }
    )
