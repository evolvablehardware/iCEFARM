"""Starts the worker."""
import logging
import sys
import tempfile
import argparse

from waitress import serve
from flask import Flask, request, Response, jsonify

from usbipice.worker.device import DeviceManager
from usbipice.worker import Config

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

    manager = DeviceManager(config, logger)

    app = Flask(__name__)

    @app.get("/heartbeat")
    def heartbeat():
        return Response(status=200)

    @app.get("/reserve")
    def reserve():
        if request.content_type != "application/json":
            return Response(status=400)

        # TODO client
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

    @app.get("/request")
    def unbind():
        if request.content_type == "application/json":
            try:
                json = request.get_json()
            except Exception:
                return Response(status=400)

            value = manager.handleRequest(json)
            if value is None:
                return Response(status=400)

            return jsonify(value)

        elif request.content_type.startswith("multipart/form-data"):
            json = {}
            for key in request.form:
                items = request.form.getlist(key)
                if len(items) != 1:
                    return Response(status=400)

                json[key] = items[0]

            if "files" in json:
                return Response(status=400)

            files = {}

            try:
                for key in request.files:
                    file = request.files.getlist(key)
                    if len(file) != 1:
                        raise Exception

                    file = file[0]

                    temp = tempfile.NamedTemporaryFile()
                    file.save(temp.name)
                    files[key] = temp
            except Exception:
                for file in files.values():
                    file.close()

                return Response(400)

            json["files"] = files

            value = manager.handleRequest(json)

            for file in files.values():
                file.close()

            if value is None:
                return Response(status=400)

            return jsonify(value)

        else:
            return Response(status=400)


    serve(app, port=config.getPort())

if __name__ == "__main__":
    main()
