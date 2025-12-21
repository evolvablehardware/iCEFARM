"""Starts the worker."""
import os
import logging
import sys
import threading
import json

from flask import Flask, Response
from flask_socketio import SocketIO
from socketio import AsyncServer, ASGIApp
from asgiref.wsgi import WsgiToAsgi

from usbipice.worker.device import DeviceManager
from usbipice.worker import Config, EventSender

from usbipice.utils import RemoteLogger, inject_and_return_json, flask_socketio_adapter_connect, flask_socketio_adapter_on, SyncAsyncServer

# 100 bitstreams
MAX_REQUEST_SIZE = 104.2 * 8000 * 100

def create_app(app, socketio, config, logger):
    logger = RemoteLogger(logger, config.getControl(), config.getName())

    event_sender = EventSender(socketio, config.getDatabase(), logger)
    manager = DeviceManager(event_sender, config, logger)

    sock_id_to_client_id = {}
    id_lock = threading.Lock()

    @app.get("/heartbeat")
    def heartbeat():
        return Response(status=200)

    @app.get("/reserve")
    @inject_and_return_json
    def reserve(serial: str, kind: str, args: dict):
        return manager.reserve(serial, kind, args)

    @app.get("/unreserve")
    @inject_and_return_json
    def devices_bus(serial: str):
        return manager.unreserve(serial)

    @socketio.on("connect")
    @flask_socketio_adapter_connect
    def connection(sid, environ, auth):
        client_id = auth.get("client_id")
        if not client_id:
            logger.warning("socket connection without client id")
            return

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

        event_sender.removeSocket(client_id)


    @socketio.on("request")
    @flask_socketio_adapter_on
    def handle(sid, data):
        with id_lock:
            client_id = sock_id_to_client_id.get(sid)

        if not client_id:
            logger.warning("socket sent request but has no known client id")
            return

        try:
            data = json.loads(data)
        except Exception:
            logger.error(f"failed to load json string from client {client_id}")
            return

        serial = data.get("serial")
        event = data.get("event")
        contents = data.get("contents")

        if not serial or not event or not contents:
            logger.error(f"bad request packet from client {client_id}")
            return

        if isinstance(serial, list):
            for s in serial:
                thread = threading.Thread(target=lambda : manager.handleRequest(s, event, contents), name="socket-request")
                thread.start()

        else:
            manager.handleRequest(serial, event, contents)

def run_debug():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.warning("Running in debug mode")

    config_path = os.environ.get("USBIPICE_WORKER_CONFIG")
    if not config_path:
        config_path = None
    config = Config(path=config_path)

    app = Flask(__name__)
    socketio = SocketIO(app, max_http_buffer_size=MAX_REQUEST_SIZE)
    create_app(app, socketio, config, logger)
    socketio.run(app, port=config.getPort(), allow_unsafe_werkzeug=True, host="0.0.0.0")

def run_uvicorn():
    # TODO
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logging.basicConfig(filemode="a", filename="worker_logs")
    logger.addHandler(logging.StreamHandler(sys.stdout))

    config_path = os.environ.get("USBIPICE_WORKER_CONFIG")
    if not config_path:
        config_path = None
    config = Config(path=config_path)

    app = Flask(__name__)
    socketio = SyncAsyncServer(async_mode="asgi", max_http_buffer_size=MAX_REQUEST_SIZE)
    create_app(app, socketio, config, logger)
    app = WsgiToAsgi(app)

    return ASGIApp(socketio, app)

if __name__ == "__main__":
    run_debug()
