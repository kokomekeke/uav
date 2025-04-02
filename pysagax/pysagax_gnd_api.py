import logging
import os

from flask_cors import CORS
from flask_socketio import SocketIO

from flask import Flask
from flask_marshmallow_openapi import OpenAPI, OpenAPISettings
from werkzeug.middleware.proxy_fix import ProxyFix

# TODO: mi az oka ennek???
platform = None
try:
    from pysagax.gnd.api.api import api

    platform = 'LINUX'
except ImportError:
    from pysagax.gnd.api import api

    platform = 'WIN'

from pysagax.gnd.database import db

app = Flask(__name__)
CORS(app, resources={r"*": {"origins": "*"}}, supports_credentials=True)
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info(f"platform is {platform}")


@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")


@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")


@socketio.on('ping')
def ping():
    logger.info('Ping received from client')
    socketio.emit('pong')


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
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )


def run_api():
    host = "0.0.0.0"
    port = 5000
    logger.info(f"Starting API on http://{host}:{port}")
    socketio.run(app, host=host, port=port)


if __name__ == '__main__':
    run_api()
