import os
import logging
import sys
import threading

from flask import Flask, request, Response, jsonify
from flask_socketio import SocketIO
from waitress import serve

from usbipice.control import Control, Heartbeat, HeartbeatConfig
from usbipice.utils import DeviceEventSender

def argify_json(parms: list[str], types: list[type]):
    """Obtains the json values of keys in the list from the flask Request and unpacks them into fun, starting with the 0 index."""
    if request.content_type != "application/json":
        return False
    try:
        json = request.get_json()
    except Exception:
        return False

    args = []

    for p, t in zip(parms, types):
        value = json.get(p)
        if value is None or not isinstance(value, t):
            return False
        args.append(value)

    if len(args) != len(parms):
        return False

    return args

def expect(fn, arg):
    if not arg or (out := fn(*arg)) is False:
        return Response(status=400)

    return jsonify(out)

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        raise Exception("USBIPICE_DATABASE not configured")

    SERVER_PORT = int(os.environ.get("USBIPICE_CONTROL_PORT", "8080"))
    logger.info(f"Running on port {SERVER_PORT}")


    event_sender = DeviceEventSender(DATABASE_URL, logger)
    control = Control(DATABASE_URL, event_sender, logger)

    heartbeat_config = HeartbeatConfig()
    heartbeat = Heartbeat(event_sender, DATABASE_URL, heartbeat_config, logger)
    heartbeat.start()

    app = Flask(__name__)
    socketio = SocketIO(app)

    sock_id_to_client_id = {}
    id_lock = threading.Lock()

    @app.get("/reserve")
    def make_reservations():
        return expect(control.reserve, argify_json(["amount", "name", "kind", "args"], [int, str, str, dict]))

    @app.get("/extend")
    def extend():
        return expect(control.extend, argify_json(["name", "serials"], [str, list]))

    @app.get("/extendall")
    def extendall():
        return expect(control.extendAll, argify_json(["name"], [str]))

    @app.get("/end")
    def end():
        return expect(control.end, argify_json(["name", "serials"], [str, list]))

    @app.get("/endall")
    def endall():
        return expect(control.end, argify_json(["name"], [str]))

    @app.get("/log")
    def log():
        if not (args := argify_json(["logs", "name"], [list, str])):
            return Response(status=400)

        control.log(*args, request.remote_addr[0])
        return Response(status=200)

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


    serve(app, port=SERVER_PORT)

if __name__ == "__main__":
    main()
