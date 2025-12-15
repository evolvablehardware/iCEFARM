"""Starts the worker."""
import logging
import sys
import argparse
import threading
import json

from flask import Flask, request, Response
from flask_socketio import SocketIO

from usbipice.worker.device import DeviceManager
from usbipice.worker import Config, EventSender

from usbipice.utils import RemoteLogger, inject_and_return_json

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logging.basicConfig(filemode="a", filename="worker_logs")
    logger.addHandler(logging.StreamHandler(sys.stdout))

    parser = argparse.ArgumentParser(
        prog="Worker Process",
        description="Runs devices for clients to connect to."
    )

    parser.add_argument("-c", "--config", help="Configuration file", default=None)
    args = parser.parse_args()
    config = Config(path=args.config)

    app = Flask(__name__)
    socketio = SocketIO(app)

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
    def connection(auth):
        client_id = auth.get("client_id")
        if not client_id:
            logger.warning("socket connection without client id")
            return

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

        event_sender.removeSocket(client_id)


    @socketio.on("request")
    def handle(data):
        with id_lock:
            client_id = sock_id_to_client_id.get(request.sid)

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

        manager.handleRequest(serial, event, contents)

    socketio.run(app, port=8081, host="0.0.0.0", debug=False)

if __name__ == "__main__":
    main()
