import marshmallow as ma
from flask_marshmallow.sqla import SQLAlchemyAutoSchema

from pysagax.gnd.database import (
    AreaOfInterestEntity,
    ComIntDetectionEntity,
    ComIntEventEntity,
    ConfigurationEntity,
    FreqOfInterestEntity,
    UAVEntity,
    UAVEventEntity,
    db,
)


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


class GeoJSONSchema(ma.Schema):
    type = ma.fields.String()
    name = ma.fields.String()
    crs = ma.fields.Dict()
    features = ma.fields.List(ma.fields.Dict())
