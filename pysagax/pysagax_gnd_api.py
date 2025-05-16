import logging
import os
import time
from queue import Queue

from flask_cors import CORS
from flask_socketio import SocketIO, disconnect
from threading import Thread
from typing import Optional

from flask import Blueprint, Flask, jsonify, url_for
from flask_marshmallow import Marshmallow
from flask_marshmallow_openapi import OpenAPI, OpenAPISettings, open_api
from flask_sqlalchemy import SQLAlchemy as FlaskSQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

from pysagax.common.loop import Loop
from pysagax.gnd.api.api import api
from pysagax.gnd.database import db
from pysagax.gnd.api.api_utils import _set_queues

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")


@socketio.on("connect")
def handle_connect():
    print("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


@socketio.on("ping")
def ping():
    print("Ping received from client")
    socketio.emit("pong")


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
if "PYSAGAX_GND_PROXY_FIX" in os.environ:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


def run_api(
    q_to_command_engine: Optional[Queue] = None,
    q_from_command_engine: Optional[Queue] = None,
):
    print("Starting api...")

    _set_queues(q_to_command_engine, q_from_command_engine)

    socketio.run(app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    run_api()
