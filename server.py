from blacksheep import get, Application, json, Response, Request
from blacksheep.server.sse import ServerSentEvent, ServerSentEventsResponse
import uvicorn
import logging
import sys
from werkzeug.utils import secure_filename
from threading import Lock
import atexit
import sys
import os
import urllib.parse
import requests

from DeviceManager import DeviceManager, Firmware
from utils import getIp

PORT = 5000

# No way to get from blacksheep since its run by uvicorn
# If we want to send from main to server process its worse


if __name__ == "__main__":
    # It does not look like uvicorn allows args to passed
    # They will be lost when uvicorn runs main again,
    # so we save them as env variables as a workaround
    if len(sys.argv) == 1:
        os.environ["SERVERCONF_EXPORT_USBIP"] = "1"
    elif len(sys.argv) == 2:
        if sys.argv[1] == "local":
            os.environ["SERVERCONF_EXPORT_USBIP"] = "0"
        else:
            raise Exception("Unknown args")

    uvicorn.run("server:app", host="0.0.0.0", port=PORT)
else:
    # this is run by the server process
    ip = getIp()

    export_usbip = os.getenv("SERVERCONF_EXPORT_USBIP") == "1"
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    manager = DeviceManager(logger, export_usbip=export_usbip)

    atexit.register(lambda : manager.onExit())

    app = Application()

@get("/devices/all")
def devices_all():
    return json(manager.getDevices())

@get("/devices/available")
def devices_available():
    return json(manager.getDevicesAvailable())

@get("/devices/bus/{device}")
def devices_bus(device: str):
    bus = manager.getDeviceExportedBus(device)

    if bus != False:
        return json(bus) 
    
    return Response(400)

@get("/devices/reserve/{device}")
async def devices_reserve_put(request: Request, device: str):
    data = await request.form()
    if "callback" in data:
        def callback(dev):
            requests.get(f"{data["callback"]}/{urllib.parse.quote_plus(ip)}/{dev.exported_busid}")

    res = manager.reserve(device, usbip_subscription=callback)

    if res:
        return json({})
    
    return Response(403)

@get("/devices/unreserve/{device}")
def devices_reserve_delete(device: str):
    res = manager.unreserve(device)

    if res:
        return json({})
    
    return Response(403)

@get("/devices/flash/{device}")
async def devices_flash(request: Request, device: str):
    data = await request.form()

    if "name" not in data:
        return Response(400)
    
    name = data["name"]
    sec_name = "firmware/" + secure_filename(name)

    if "firmware" not in data:
        return Response(400)
    
    with open(sec_name, "wb") as f:
        f.write(data["firmware"][0].data)
    
    lock = Lock()
    lock.acquire()

    res = manager.uploadFirmware(device, Firmware(name, sec_name, callback=lambda _ : lock.release()))

    if not res:
        return Response(400)

    async def events_provider():
        yield ServerSentEvent("started bootloader mode")
        lock.acquire()
        yield ServerSentEvent("upload complete")
    
    return ServerSentEventsResponse(events_provider)
