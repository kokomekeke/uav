import logging
import os
import time
from queue import Queue

from flask_cors import CORS
from flask_socketio import SocketIO
from typing import Optional

from flask import Flask, request
from flask_marshmallow_openapi import OpenAPI, OpenAPISettings
from werkzeug.middleware.proxy_fix import ProxyFix

from pysagax.common.loop import Loop

try:
    from pysagax.gnd.api.api import api

    platform = "WINDOWS"
except ImportError:
    from pysagax.gnd.api import api

    platform = "LINUX"

from pysagax.gnd.database import db
from pysagax.gnd.api.api_utils import _set_queues

# TODO: rework this file so that
#           - logger level should come from pysagax_gnd.py
#           - initialization steps should be separated from socketio funcs
#           - no hard-coded constants: parse from cli or config file
#           - finalize passing queues in run_api

app = Flask(__name__)
CORS(
    app,
    resources={
        r"*": {
            "origins": ["http://localhost:5173"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "Accept",
                "Cache-Control",
            ],
            "expose_headers": ["Content-Type", "Cache-Control"],
            "supports_credentials": True,  # Important for EventSource with wildcard origin
        }
    },
)

socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    ping_timeout=45,
    ping_interval=15,
    allow_upgrades=True,
    transports=["websocket", "polling"],  # only websocket transport
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

logger.info(f"ASDFASDFASDFplatform is {platform}")


@socketio.on("connect")
def handle_connect(_):
    logger.info(f"Client connected - Session ID: {request.sid}")
    socketio.emit("connect_ack", {"status": "connected", "session_id": request.sid})


@socketio.on("disconnect")
def handle_disconnect():
    logger.info(f"Client disconnected - Session ID: {request.sid}")


@socketio.on("ping")
def ping(data):
    logger.info(f"Ping received from client - Session ID: {request.sid}")
    socketio.emit("pong", {"timestamp": time.time()})


@socketio.on("force_disconnect")
def handle_force_disconnect():
    logger.info(f"Force disconnect requested - Session ID: {request.sid}")
    socketio.disconnect(request.sid)


if "DATABASE_URI" in os.environ:
    logger.info(f"environment variable DATABASE_URI= {os.environ['DATABASE_URI']}")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URI"]
else:
    logger.info("DATABASE_URI environment variable not set")
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
    measurement_to_stream_queue: Optional[Queue] = None,
    level: str = "INFO",
):
    logger.setLevel(level.upper())

    # TODO: egységes queue átadási módszerek
    _set_queues(q_to_command_engine, q_from_command_engine)
    app.measurement_to_stream_queue = measurement_to_stream_queue

    host = "0.0.0.0"
    port = 5000
    logger.info(f"Starting API on http://{host}:{port}")

    socketio.run(
        app,
        host=host,
        port=port,
        debug=logger.isEnabledFor(
            logging.DEBUG
        ),  # True if logging level is DEBUG or lower (TRACE)
    )


if __name__ == "__main__":
    run_api()
