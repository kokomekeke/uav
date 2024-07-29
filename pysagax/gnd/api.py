import textwrap

import flask
import marshmallow as ma
from flask import jsonify
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


@open_api.get_list(ComIntDetectionSchema)
@api.route("/comintdetection/")
def comintdetection_list():
    all_detections = ComIntDetectionEntity.query.all()
    return jsonify(comintdetections_schema.dump(all_detections))


@open_api.get_detail(ComIntDetectionSchema)
@api.route("/comintdetection/<id>", methods=["GET"])
def comintdetection_detail(id):
    comintdetection = ComIntDetectionEntity.query.get(id)
    return comintdetection_schema.jsonify(comintdetection)


@open_api.get_list(UAVSchema)
@api.route("/uav/")
def uav_list():
    all_uavs = UAVEntity.query.all()
    return jsonify(uavs_schema.dump(all_uavs))


@open_api.get_detail(UAVSchema)
@api.route("/uav/<int:id>", methods=["GET"])
def uav_detail(id):
    uav = UAVEntity.query.get(id)
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


@open_api.patch(request_schema=UAVCreateSchema, response_schema=UAVSchema)
@api.route("/uav/<int:id>", methods=["PATCH"])
def uav_update(id):
    data = UAVCreateSchema(many=False).load(flask.request.json)
    uav = UAVEntity.query.get(id)
    uav.active = data["active"]
    uav.uav_label = data["uav_label"]
    uav.uav_address = data["uav_address"]
    db.session.commit()
    return uav_schema.jsonify(uav)


# endpoint to delete user
@open_api.delete(UAVSchema)
@api.route("/uav/<int:id>", methods=["DELETE"])
def user_delete(id):
    uav = UAVEntity.query.get(id)
    db.session.delete(uav)
    db.session.commit()

    return jsonify({})
