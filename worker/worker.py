from flask import Flask, request, Response
import logging
import sys
import atexit
import sys
import os
from waitress import serve

from worker.DeviceManager import DeviceManager
from worker.WorkerDatabase import WorkerDatabase
from utils.utils import getIp

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    IP = os.environ.get("USBIPICE_EXPORTED_IP")
    SERVER_PORT = os.environ.get("USBIPICE_EXPORTED_SERVER_PORT")
    USBIP_PORT = os.environ.get("USBIPICE_EXPORTED_USBIP_PORT")
    CLIENT_NAME = os.environ.get("USBIPICE_CLIENT")

    if not DATABASE_URL:
        logger.critical("USBIPICE_DATABASE not configured, exiting")
        raise Exception("USBIPICE_DATABASE not configured")

    if not CLIENT_NAME:
        logger.critical("USBIPICE_CLIENT not configured, exiting")
        raise Exception("USBIPICE_CLIENT not configured")

    if not IP:
        IP = getIp()
        logger.warning(f"USBIPICE_EXPORTED_IP not configured, defaulting to {IP}")

    if not SERVER_PORT:
        SERVER_PORT= 8080
        logger.warning(f"USBIPICE_EXPORTED_SERVER_PORT not configured, defaulting to {SERVER_PORT}")
    else:
        SERVER_PORT = int(SERVER_PORT)
    
    if not USBIP_PORT:
        USBIP_PORT = 3240
        logger.warning(f"USBIPICE_EXPORTED_USBIP_PORT not configured, defaulting to {USBIP_PORT}")
    else:
        USBIP_PORT = int(USBIP_PORT)
    
    db = WorkerDatabase(DATABASE_URL, CLIENT_NAME, IP, SERVER_PORT, USBIP_PORT, logger)
    manager = DeviceManager(db, logger)

    atexit.register(lambda : manager.onExit())

    app = Flask(__name__)

    @app.get("/heartbeat")
    def heartbeat():
        return Response(status=200)

    @app.get("/unreserve")
    async def devices_bus():
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

    serve(app, port=SERVER_PORT)

if __name__ == "__main__":
    main()
