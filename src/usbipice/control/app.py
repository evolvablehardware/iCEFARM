import os
import logging
import sys
import threading

from flask import Flask, request
from flask_socketio import SocketIO

from usbipice.control import Control, Heartbeat, HeartbeatConfig, ControlEventSender
from usbipice.utils import inject_and_return_json

class ControlLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[Control] {msg}", kwargs

def main():
    base_logger = logging.getLogger(__name__)
    base_logger.setLevel(logging.DEBUG)
    base_logger.addHandler(logging.StreamHandler(sys.stdout))

    logger = ControlLogger(base_logger)

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        raise Exception("USBIPICE_DATABASE not configured")

    SERVER_PORT = int(os.environ.get("USBIPICE_CONTROL_PORT", "8080"))
    logger.info(f"Running on port {SERVER_PORT}")


    app = Flask(__name__)
    socketio = SocketIO(app)

    sock_id_to_client_id = {}
    id_lock = threading.Lock()

    event_sender = ControlEventSender(socketio, DATABASE_URL, logger)
    control = Control(event_sender, DATABASE_URL, logger)

    heartbeat_config = HeartbeatConfig()
    heartbeat = Heartbeat(event_sender, DATABASE_URL, heartbeat_config, logger)
    heartbeat.start()

    @app.get("/reserve")
    @inject_and_return_json
    def make_reservations(amount: int, name: str, kind: str, args: dict):
        return control.reserve(name, amount, kind, args)

    @app.get("/extend")
    @inject_and_return_json
    def extend(name: str, serials: list[str]):
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
    def connection(auth):
        client_id = auth.get("client_id")
        if not client_id:
            logger.warning("socket connection without client id")
            return

        logger.info(f"client {client_id} connected")

        with id_lock:
            sock_id_to_client_id[request.sid] = client_id

        event_sender.addSocket(request.sid, client_id)

    @socketio.on("disconnect")
    def disconnect(reason):
        with id_lock:
            client_id = sock_id_to_client_id.pop(request.sid, None)

        if not client_id:
            logger.warning("disconnected socket had no known client id")
            return

        logger.info(f"client {client_id} disconnected")

        event_sender.removeSocket(client_id)


    #TODO
    socketio.run(app, port=SERVER_PORT, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    main()
