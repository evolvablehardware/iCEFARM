"""Starts the worker."""
import logging
import sys
import argparse
import threading
import json

from waitress import serve
from flask import Flask, request, Response
from flask_socketio import SocketIO

from usbipice.worker.device import DeviceManager
from usbipice.worker import Config, EventSender

from usbipice.utils import RemoteLogger

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
    def reserve():
        if request.content_type != "application/json":
            return Response(status=400)

        try:
            json = request.get_json()
        except Exception:
            return Response(status=400)

        status = 200 if manager.reserve(json) else 400

        return Response(status=status)

    @app.get("/unreserve")
    def devices_bus():
        if request.content_type != "application/json":
            return Response(status=400)

        try:
            json = request.get_json()
        except Exception:
            return Response(status=400)

        serial = json.get("serial")

        if not serial:
            return Response(status=400)

        if manager.unreserve(serial):
            return Response(status=200)
        else:
            return Response(status=400)

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

        manager.handleRequest(data)

    socketio.run(app, port=8081)

if __name__ == "__main__":
    main()
