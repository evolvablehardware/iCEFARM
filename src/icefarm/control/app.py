import os
import logging
import sys
import threading

from flask import Flask, request, send_file
from flask_socketio import SocketIO
from socketio import ASGIApp
from asgiref.wsgi import WsgiToAsgi

from icefarm.control import Control, Heartbeat, HeartbeatConfig, ControlEventSender
from icefarm.utils.web import SyncAsyncServer
from icefarm.utils.web import flask_socketio_adapter_connect, flask_socketio_adapter_on, inject_and_return_json

class ControlLogger(logging.LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return f"[Control] {msg}", kwargs

def create_app(app: Flask, socketio: SocketIO | SyncAsyncServer, base_logger: logging.Logger):
    logger = ControlLogger(base_logger)

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        raise Exception("USBIPICE_DATABASE not configured")

    sock_id_to_client_id = {}
    id_lock = threading.Lock()

    event_sender = ControlEventSender(socketio, DATABASE_URL, logger)
    control = Control(event_sender, DATABASE_URL, logger)

    heartbeat_config = HeartbeatConfig()
    heartbeat = Heartbeat(event_sender, DATABASE_URL, heartbeat_config, logger)
    heartbeat.start()

    @app.get("/")
    def get_app():
        return control.getApp()

    @app.get("/style.css")
    def style():
        return send_file("./assets/style.css")

    @app.get("/reboot")
    @inject_and_return_json
    def reboot(serials: list[str]):
        return control.reboot(serials)

    @app.get("/delete")
    @inject_and_return_json
    def delete(serials: list[str]):
        return control.delete(serials)

    @app.get("/available")
    def available():
        return control.getAmountAvailable()

    @app.get("/devices")
    def devices():
        return control.getDevicesAvailable()

    @app.get("/reserve")
    @inject_and_return_json
    def make_reservations(amount: int, name: str, kind: str, args: dict):
        return control.reserve(name, amount, kind, args)

    @app.get("/reserveserials")
    @inject_and_return_json
    def make_specific_reservations(name: str, kind: str, args: dict, serials: list[str]):
        return control.reserveSerials(name, serials, kind, args)

    @app.get("/extend")
    @inject_and_return_json
    def extend(name: str, serials: list):
        return control.extend(name, serials)

    @app.get("/extendall")
    @inject_and_return_json
    def extendall(name: str):
        return control.extendAll(name)

    @app.get("/end")
    @inject_and_return_json
    def end(name: str, serials: list):
        return control.end(name, serials)

    @app.get("/endall")
    @inject_and_return_json
    def endall(name: str):
        return control.endAll(name)

    @app.get("/log")
    @inject_and_return_json
    def log(name: str, logs: list):
        for row in logs:
            if len(row) != 2:
                continue

            level, msg = row[0], row[1]
            base_logger.log(level, f"[{name}@{request.remote_addr[0]}] {msg}")

        return True

    @socketio.on("connect")
    @flask_socketio_adapter_connect
    def connection(sid, environ, auth):
        client_id = auth.get("client_id")
        if not client_id:
            logger.warning("socket connection without client id")
            return

        logger.info(f"client {client_id} connected")

        with id_lock:
            sock_id_to_client_id[sid] = client_id

        event_sender.addSocket(sid, client_id)

    @socketio.on("disconnect")
    @flask_socketio_adapter_on
    def disconnect(sid, reason):
        with id_lock:
            client_id = sock_id_to_client_id.pop(sid, None)

        if not client_id:
            logger.warning("disconnected socket had no known client id")
            return

        logger.info(f"client {client_id} disconnected")

        event_sender.removeSocket(client_id)

def run_debug():
    SERVER_PORT = int(os.environ.get("USBIPICE_CONTROL_PORT", "8080"))

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.warning("Running in debug mode")

    app = Flask(__name__)

    socketio = SocketIO(app)
    create_app(app, socketio, logger)
    socketio.run(app, port=SERVER_PORT, allow_unsafe_werkzeug=True, host="0.0.0.0")

def run_uvicorn():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    app = Flask(__name__)
    socketio = SyncAsyncServer(async_mode="asgi")
    create_app(app, socketio, logger)
    app = WsgiToAsgi(app)

    return ASGIApp(socketio, app)


if __name__ == "__main__":
    run_debug()
