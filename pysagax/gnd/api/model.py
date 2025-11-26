import marshmallow as ma
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field

from pysagax.gnd.database import (
    AreaOfInterestEntity,
    ComIntDetectionEntity,
    ComIntGeoLocEntity,
    ComIntEventEntity,
    ConfigurationEntity,
    FreqOfInterestEntity,
    UAVEntity,
    UAVEventEntity,
    db,
)


# ======================================================================
#  SQLALCHEMY-ALAPÚ SÉMÁK (AUTO-GENERATED)
# ======================================================================

class BaseSQLAlchemySchema(SQLAlchemyAutoSchema):
    """
    Közös alap séma:
    - session szükséges a Marshmallow-SQLAlchemy-hez
    - load_instance=True → automatikusan SQLAlchemy objektumot ad vissza
    """
    class Meta:
        sqla_session = db.session
        load_instance = True
        include_relationships = True
        include_fk = True


# ---------------- UAV ----------------

class UAVSchema(BaseSQLAlchemySchema):
    class Meta(BaseSQLAlchemySchema.Meta):
        model = UAVEntity


class UAVEventSchema(BaseSQLAlchemySchema):
    class Meta(BaseSQLAlchemySchema.Meta):
        model = UAVEventEntity


# ---------------- COMINT ----------------

class ComIntEventSchema(BaseSQLAlchemySchema):
    class Meta(BaseSQLAlchemySchema.Meta):
        model = ComIntEventEntity


class ComIntDetectionSchema(BaseSQLAlchemySchema):
    class Meta(BaseSQLAlchemySchema.Meta):
        model = ComIntDetectionEntity


# ---------------- CONFIGURATION ----------------

class ConfigurationSchema(BaseSQLAlchemySchema):
    class Meta(BaseSQLAlchemySchema.Meta):
        model = ConfigurationEntity


# ---------------- AOI / FOI ----------------

class AreaOfInterestSchema(BaseSQLAlchemySchema):
    class Meta(BaseSQLAlchemySchema.Meta):
        model = AreaOfInterestEntity


class FreqOfInterestSchema(BaseSQLAlchemySchema):
    class Meta(BaseSQLAlchemySchema.Meta):
        model = FreqOfInterestEntity


# ======================================================================
#  KÉZI VALIDÁCIÓS SÉMÁK (CREATE / UPDATE INPUTOK)
# ======================================================================

class UAVCreateSchema(ma.Schema):
    uav_label = ma.fields.String(allow_none=True)
    uav_address = ma.fields.String(required=True)
    active = ma.fields.Boolean(required=True)


class UAVUpdateSchema(ma.Schema):
    uav_label = ma.fields.String(allow_none=True)
    uav_address = ma.fields.String()
    active = ma.fields.Boolean()


# ======================================================================
#  GEOJSON OUTPUT SCHEMA
# ======================================================================

class GeoJSONSchema(ma.Schema):
    type = ma.fields.String(required=True)
    name = ma.fields.String(required=False)
    crs = ma.fields.Dict(required=False)
    features = ma.fields.List(ma.fields.Dict(), required=True)
