import logging
import json
import time
from queue import Empty

from flask import request, jsonify, make_response, current_app, Response, stream_with_context
from flask_smorest import Blueprint, abort
from sqlalchemy.sql import text

import pysagax.message.command_pb2 as proto_cmd
from google.protobuf.json_format import ParseDict, MessageToDict

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

logger = logging.getLogger("api")

# ----------------------------------------------------------------------
# SMOREST BLUEPRINT
# ----------------------------------------------------------------------

api = Blueprint(
    "api",
    __name__,
    url_prefix="/v1",
    description="PySAGAX GND API endpoints"
)


# ----------------------------------------------------------------------
# UTIL
# ----------------------------------------------------------------------

def not_found_error(message):
    abort(404, message=message)


# ----------------------------------------------------------------------
# ENDPOINTS
# ----------------------------------------------------------------------

# ---------------------------
# COMINT DETECTION LIST
# ---------------------------
@api.route("/comintdetection/list_from/<int:id>")
@api.response(200, ComIntDetectionSchema(many=True))
def comintdetection_list(id):
    all_detections = (
        ComIntDetectionEntity.query
        .order_by(ComIntDetectionEntity.detection_id.desc())
        .filter(ComIntDetectionEntity.detection_id >= id)
        .all()
    )
    return all_detections


# ---------------------------
# COMINT GEOJSON FROM ID
# ---------------------------
@api.route("/comintdetection/geojson/list_from/<int:id>")
@api.response(200, GeoJSONSchema)
def comintdetection_geojson_list(id):
    all_detections = (
        ComIntDetectionEntity.query
        .order_by(ComIntDetectionEntity.detection_id.asc())
        .filter(ComIntDetectionEntity.detection_id >= id)
        .all()
    )

    return {
        "type": "FeatureCollection",
        "name": "ComIntDetection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [geojson_feature_from_detection(det) for det in all_detections],
    }


# ---------------------------
# COMINT GEOJSON LAST N
# ---------------------------
@api.route("/comintdetection/geojson/list_last/<int:limit>")
@api.response(200, GeoJSONSchema)
def comintdetection_geojson_list_last(limit):

    stride = request.args.get("stride", 1, type=int)
    uavs = request.args.getlist("uav", type=int)
    roi_ids = request.args.getlist("roi_id", type=int)
    event_ids = request.args.getlist("e_id", type=int)

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

    where_clause_parts = []
    if uavs:
        where_clause_parts.append("uav_id IN :uavs")
    if roi_ids:
        where_clause_parts.append("roi_identifier IN :roi_ids")
    if event_ids:
        where_clause_parts.append("event_id IN :event_id")

    where_clause = "WHERE " + " AND ".join(where_clause_parts) if where_clause_parts else ""
    sql = sql.format(where_clause=where_clause)

    query = db.session.query(ComIntDetectionEntity).from_statement(text(sql))

    params = {"stride": stride, "limit": limit}
    if uavs:
        params["uavs"] = tuple(uavs)
    if roi_ids:
        params["roi_ids"] = tuple(roi_ids)
    if event_ids:
        params["event_id"] = tuple(event_ids)

    detections = query.params(**params).all()

    return {
        "type": "FeatureCollection",
        "name": "ComIntDetection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [geojson_feature_from_detection(det) for det in detections],
    }


# ---------------------------
# COMINT DETECTION DETAIL
# ---------------------------
@api.route("/comintdetection/<int:id>")
@api.response(200, ComIntDetectionSchema)
def comintdetection_detail(id):
    det = ComIntDetectionEntity.query.get(id)
    if not det:
        not_found_error(f"ComIntDetection {id} not found.")
    return det


# ---------------------------
# RAW GEOLOC
# ---------------------------
@api.route("/comintgeoloc/geojson/raw/list_last/<int:limit>")
@api.response(200, GeoJSONSchema)
def comintevent_raw_geojson(limit):

    stride = request.args.get("stride", 1, type=int)
    roi_ids = request.args.getlist("roi_id", type=int)

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

    params = {"stride": stride, "limit": limit}
    if roi_ids:
        params["roi_ids"] = tuple(roi_ids)

    points = db.session.query(ComIntGeoLocEntity).from_statement(text(sql)).params(**params).all()

    return {
        "type": "FeatureCollection",
        "name": "ComIntGeoLoc",
        "crs": { "type": "name",
                 "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"} },
        "features": [geojson_feature_from_geoloc(p) for p in points],
    }


# ---------------------------
# FILTERED GEOLOC
# ---------------------------
@api.route("/comintgeoloc/geojson/list_last/<int:limit>")
@api.response(200, GeoJSONSchema)
def comintevent_geojson(limit):

    stride = request.args.get("stride", 1, type=int)
    roi_ids = request.args.getlist("roi_id", type=int)

    sql = """
    WITH ranked AS (
        SELECT *
        FROM comintfilteredgeoloc
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

    params = {"stride": stride, "limit": limit}
    if roi_ids:
        params["roi_ids"] = tuple(roi_ids)

    points = db.session.query(ComIntGeoLocEntity).from_statement(text(sql)).params(**params).all()

    return {
        "type": "FeatureCollection",
        "name": "ComIntGeoLoc",
        "crs": {"type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [geojson_feature_from_geoloc(p) for p in points],
    }


# ---------------------------
# UAV LIST
# ---------------------------
@api.route("/uav/")
@api.response(200, UAVSchema(many=True))
def uav_list():
    return UAVEntity.query.order_by(UAVEntity.uav_id.asc()).all()


# ---------------------------
# UAV GEOJSON LIST
# ---------------------------
@api.route("/uav/geojson")
@api.response(200, GeoJSONSchema)
def uav_geojson_list():
    all_uavs = UAVEntity.query.order_by(UAVEntity.uav_id.asc()).all()
    return {
        "type": "FeatureCollection",
        "name": "UAV",
        "crs": { "type": "name",
                 "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"} },
        "features": [geojson_feature_from_uav(u) for u in all_uavs],
    }


# ---------------------------
# UAV DETAIL
# ---------------------------
@api.route("/uav/<int:id>")
@api.response(200, UAVSchema)
def uav_detail(id):
    uav = UAVEntity.query.get(id)
    if not uav:
        not_found_error(f"UAV {id} not found.")
    return uav


# ---------------------------
# UAV CREATE
# ---------------------------
@api.route("/uav", methods=["POST"])
@api.arguments(UAVCreateSchema)
@api.response(201, UAVSchema)
def uav_create(data):
    new_uav = UAVEntity(**data)
    db.session.add(new_uav)
    db.session.commit()
    return new_uav


# ---------------------------
# UAV UPDATE
# ---------------------------
@api.route("/uav/<int:id>", methods=["PATCH"])
@api.arguments(UAVUpdateSchema)
@api.response(200, UAVSchema)
def uav_update(data, id):
    uav = UAVEntity.query.get(id)
    if not uav:
        not_found_error(f"UAV {id} not found.")

    for key, value in data.items():
        setattr(uav, key, value)

    db.session.commit()
    return uav


# ---------------------------
# UAV DELETE
# ---------------------------
@api.route("/uav/<int:id>", methods=["DELETE"])
@api.response(200, dict)
def uav_delete(id):
    uav = UAVEntity.query.get(id)
    if not uav:
        not_found_error(f"UAV {id} not found.")
    db.session.delete(uav)
    db.session.commit()
    return {}


# ---------------------------
# COMMAND ENDPOINT (unchanged)
# ---------------------------
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
    proto_cmd.Instruction.CS_CALIBRATE_START: ("calib_command", proto_cmd.CalibrationCommand),
    proto_cmd.Instruction.CS_CALIBRATE_ABORT: None,
    proto_cmd.Instruction.CS_TURN_OFF_COMPENSATION: None,
    proto_cmd.Instruction.CS_TURN_ON_COMPENSATION: None,
    proto_cmd.Instruction.CS_READ_PHASEDIFFS_FROM_FILE: ("calib_command", proto_cmd.CalibrationCommand),
    proto_cmd.Instruction.CS_CALIBRATION_VALUES_QUERY: None,
    proto_cmd.Instruction.CS_CALIBRATION_PHASE_CHECK: None,
    proto_cmd.Instruction.AUTO_CALIBRATION_ENABLE: None,
    proto_cmd.Instruction.AUTO_CALIBRATION_DISABLE: None,
    proto_cmd.Instruction.AUTO_CALIBRATION_TRIGGER: None,
    proto_cmd.Instruction.CS_RELOAD_CONFIG: None,
    proto_cmd.Instruction.FORWARD_TO_APM: ("msg_to_apm", proto_cmd.MessageToAPM),
}

cmd_id = 0

@api.route("/command/list", methods=["GET"])
def command_list():
    result = {}

    for instruction, mapping in INSTRUCTION_MAP.items():
        instr_name = proto_cmd.Instruction.Name(instruction)

        if mapping is None:
            result[instr_name] = None
        else:
            param_name, param_type = mapping

            # param_type lehet Python type vagy protobuf class
            result[instr_name] = {
                "parameter_name": param_name,
                "parameter_type": param_type.__name__
            }

    return jsonify(result)


@api.route("/uav/<int:id>/command/<string:instruction>/", methods=["POST"])
def command(id, instruction):

    def assign_cmd(cmd, parameter_name, parameter):
        try:
            setattr(cmd, parameter_name, parameter)
        except AttributeError:
            getattr(cmd, parameter_name).CopyFrom(parameter)

    def parse_param(parameter_type, raw_data):
        try:
            parameter = parameter_type()
            ParseDict(raw_data, parameter, ignore_unknown_fields=True)
        except AttributeError:
            parameter = raw_data
        return parameter

    try:
        instruction_enum_value = proto_cmd.Instruction.Value(instruction.upper())
    except ValueError:
        abort(400, message=f"Invalid instruction '{instruction}'")

    mapping = INSTRUCTION_MAP.get(instruction_enum_value)
    if mapping is None and instruction_enum_value not in INSTRUCTION_MAP:
        abort(400, message=f"Instruction '{instruction}' not supported")

    raw_data = request.get_json() if request.is_json else {}

    # ✅ DEBUG LOG #1
    print(f"[API] Received command '{instruction}' for UAV #{id}")
    print(f"[API] Raw data: {raw_data}")

    cmd = proto_cmd.Command()

    if mapping:
        parameter_name, parameter_type = mapping
        parameter = parse_param(parameter_type, raw_data)
        # ✅ DEBUG LOG #2
        print(f"[API] Parsed parameter ({parameter_name}): {parameter}")
        assign_cmd(cmd, parameter_name, parameter)

    cmd.instruction = instruction_enum_value

    global cmd_id
    cmd.id = cmd_id
    cmd_id += 1
    # ✅ DEBUG LOG #3
    print(f"[API] Final command object: {cmd}")
    response = send_to_command_engine(target_id=id, cmd=cmd)

    # ✅ DEBUG LOG #4
    print(f"[API] Response from command engine: {response}")
    return jsonify(MessageToDict(response))


# ---------------------------
# EVENT STREAM (unchanged)
# ---------------------------
@api.route("/stream/comint_detection", methods=["GET", "OPTIONS"])
def comint_detection_stream():

    if request.method == "OPTIONS":
        return Response("", status=204, headers={
            "Access-Control-Allow-Origin": "http://localhost:5173",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Credentials": "true",
        })

    if not hasattr(current_app, "to_stream_q"):
        return make_response(jsonify({"error": "Stream queue not available"}), 503)

    app_queue = current_app.to_stream_q

    default_batch = 0.2
    batch_interval = request.args.get("interval", default_batch, type=float)
    batch_interval = max(0.01, min(batch_interval, 2.0))

    buffer_all_flag = request.args.get("buffer_all_flag", True, type=bool)

    max_connection_time = 3600

    def generate():
        start = time.perf_counter()
        last_sent = start
        buffer = []
        id_buff = {}

        while True:
            now = time.perf_counter()
            if now - start >= max_connection_time:
                yield f"data: {json.dumps({'info': 'Connection timeout reached'})}\n\n"
                break

            try:
                id_, raw = app_queue.get(timeout=0.01)
                pb_type = raw.DESCRIPTOR.name

                data = {"id": id_, pb_type: MessageToDict(raw)}
                print('d')

                if buffer_all_flag:
                    buffer.append(data)
                    if now - last_sent >= batch_interval:
                        yield f"data: {json.dumps(buffer)}\n\n"
                        buffer = []
                        last_sent = now
                else:
                    id_buff[f"{id_},{pb_type}"] = data
                    if now - last_sent >= batch_interval:
                        yield f"data: {json.dumps(list(id_buff.values()))}\n\n"
                        id_buff = {}
                        last_sent = now

            except Empty:
                pass

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


# ---------------------------
# REDOC
# ---------------------------
@api.route("/redoc")
def redoc():
    return """
    <!DOCTYPE html>
    <html>
      <head>
        <title>ReDoc</title>
        <script src="https://cdn.jsdelivr.net/npm/redoc@2.0.0-rc.72/bundles/redoc.standalone.js"></script>
      </head>
      <body>
        <redoc spec-url='/v1/openapi.json'></redoc>
      </body>
    </html>
    """
