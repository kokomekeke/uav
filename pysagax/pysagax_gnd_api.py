import logging
import os
import time
from queue import Queue
from threading import Thread
from typing import Optional

from flask import Blueprint, Flask, jsonify, url_for
from flask_marshmallow import Marshmallow
from flask_marshmallow_openapi import OpenAPI, OpenAPISettings, open_api
from flask_sqlalchemy import SQLAlchemy as FlaskSQLAlchemy

from pysagax.common.loop import Loop
from pysagax.gnd.api import api
from pysagax.gnd.database import db

app = Flask(__name__)
if "DATABASE_URI" in os.environ:
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URI"]
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql+psycopg2://pysagax_gnd:S3cret@localhost/comint"
    )
app.register_blueprint(api, url_prefix="/v1")
db.init_app(app)
conf = OpenAPISettings(
    api_version="v1",
    api_name="PySAGAX-GND API",
    app_package_name="pysagax.gnd.api",
    mounted_at="/v1",
)
conf.swagger_json_template_loader = lambda: {
    "components": {"securitySchemes": {}},
    "title": conf.api_name,
    "openapi_version": "3.0.2",
    "version": conf.api_version,
}

docs = OpenAPI(config=conf)
docs.init_app(app)
