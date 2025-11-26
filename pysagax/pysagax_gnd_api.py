import logging
import os
import time
from queue import Queue

from flask_cors import CORS
from flask_socketio import SocketIO
from typing import Optional

from flask import Flask, request
from flask_smorest import Api      # ⭐ NEW
from werkzeug.middleware.proxy_fix import ProxyFix

from pysagax.common.loop import Loop

try:
    from pysagax.gnd.api.api import api as sagax_blueprint   # ⭐ a te API blueprinted már smorest-re lesz átírva
    platform = "WINDOWS"
except ImportError:
    from pysagax.gnd.api import api as sagax_blueprint
    platform = "LINUX"

from pysagax.gnd.database import db


# ======================================================================
# FLASK APP
# ======================================================================

app = Flask(__name__)
CORS(app)

socketio = SocketIO(
    app,
    async_mode='threading',
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.info(f"platform is {platform}")


# ======================================================================
# SOCKET.IO HANDLERS (unchanged)
# ======================================================================

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


# ======================================================================
# DATABASE CONFIG
# ======================================================================

if "DATABASE_URI" in os.environ:
    logger.info(f"environment variable DATABASE_URI= {os.environ['DATABASE_URI']}")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URI"]
else:
    logger.info("DATABASE_URI environment variable not set")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql+psycopg2://pysagax_gnd:S3cret@localhost/comint"
    )

db.init_app(app)


# ======================================================================
# SMOREST API CONFIG (⭐ EZ A LÉNYEG)
# ======================================================================

app.config["API_TITLE"] = "PySAGAX-GND API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/v1"

# Swagger UI
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Redoc (opcionális)
app.config["OPENAPI_REDOC_PATH"] = "/redoc"

api = Api(app)  # ⭐ SMOREST API

# Register your blueprint
api.register_blueprint(sagax_blueprint)


# ======================================================================
# OPTIONAL PROXY FIX
# ======================================================================

if "PYSAGAX_GND_PROXY_FIX" in os.environ:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


# ======================================================================
# RUN
# ======================================================================

def run_api(
    q_to_command_engine: Optional[Queue] = None,
    q_from_command_engine: Optional[Queue] = None,
    to_stream_q: Optional[Queue] = None,
    level: str = "INFO",
):

    logger.setLevel(level.upper())

    app.q_to_command_engine = q_to_command_engine
    app.q_from_command_engine = q_from_command_engine
    app.to_stream_q = to_stream_q

    host = "0.0.0.0"
    port = 5000
    logger.info(f"Starting API on http://{host}:{port}")

    socketio.run(
        app,
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    run_api()
