from blacksheep import get, post, Application, json, Response, Request, FromFiles
import uvicorn
import logging
import sys
from werkzeug.utils import secure_filename

from DeviceManager import DeviceManager, Firmware

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8080)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

manager = DeviceManager(logger, export_usbip=True)

app = Application()

@get("/devices/all")
def devices_all():
    return json(manager.getDevices())

@get("/devices/available")
def devices_available():
    return json(manager.getDevicesAvailable())

@get("/devices/bus/{device}")
def devices_bus(device: str):
    bus = manager.getDeviceExportedBuses(device)

    if bus != False:
        return json(device) 
    
    return Response(400)

@get("/devices/reserve/{device}")
def devices_reserve_put(device: str):
    res = manager.reserve(device)
    return Response(200 if res else 403)

@get("/devices/unreserve/{device}")
def devices_reserve_delete(device: str):
    res = manager.unreserve(device)
    return Response(200 if res else 403)


@post("/devices/flash/{device}")
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

    res = manager.uploadFirmware(device, Firmware(name, sec_name))

    return Response(200 if res else 403)



