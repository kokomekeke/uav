import textwrap

import flask
import marshmallow as ma
from flask import jsonify, make_response
from flask_marshmallow.sqla import SQLAlchemyAutoSchema
from flask_marshmallow_openapi import Securities, open_api

from pysagax.gnd.database import (
    AreaOfInterestEntity,
    ComIntDatabase,
    ComIntDetectionEntity,
    ComIntEventEntity,
    ConfigurationEntity,
    FreqOfInterestEntity,
    UAVEntity,
    UAVEventEntity,
    db,
)

api = flask.Blueprint("api", __name__)


class UAVSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = UAVEntity
        include_relationships = True
        load_instance = True
        include_fk = True


class UAVCreateSchema(ma.Schema):
    uav_label = ma.fields.String(allow_none=True, required=False)
    uav_address = ma.fields.String(allow_none=False, required=True)
    active = ma.fields.Boolean(allow_none=False, required=True)


class UAVUpdateSchema(ma.Schema):
    uav_label = ma.fields.String(allow_none=True, required=False)
    uav_address = ma.fields.String(allow_none=False, required=False)
    active = ma.fields.Boolean(allow_none=False, required=False)


class UAVEventSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = UAVEventEntity
        include_relationships = True
        include_fk = True
        load_instance = True


class ComIntEventSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ComIntEventEntity
        include_relationships = True
        include_fk = True
        load_instance = True


class ComIntDetectionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ComIntDetectionEntity
        include_fk = True
        load_instance = True


class ConfigurationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ConfigurationEntity
        include_relationships = True
        include_fk = True
        load_instance = True


class AreaOfInterestSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AreaOfInterestEntity
        include_fk = True
        load_instance = True


class FreqOfInterestSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = FreqOfInterestEntity
        include_fk = True
        load_instance = True


comintdetections_schema = ComIntDetectionSchema(many=True)
comintdetection_schema = ComIntDetectionSchema()

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


@open_api.get_detail(ComIntDetectionSchema)
@api.route("/comintdetection/<int:id>", methods=["GET"])
def comintdetection_detail(id):
    comintdetection = ComIntDetectionEntity.query.get(id)
    return comintdetection_schema.jsonify(comintdetection)


@open_api.get_list(UAVSchema)
@api.route("/uav/")
def uav_list():
    all_uavs = UAVEntity.query.order_by(UAVEntity.uav_id.asc()).all()
    return jsonify(uavs_schema.dump(all_uavs))


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


# endpoint to delete user
@open_api.delete(UAVSchema)
@api.route("/uav/<int:id>", methods=["DELETE"])
def user_delete(id):
    uav = UAVEntity.query.get(id)
    if uav is None:
        return not_found_error(f"UAV {id} not found.")
    db.session.delete(uav)
    db.session.commit()

    return jsonify({})
