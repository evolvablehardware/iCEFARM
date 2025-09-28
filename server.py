import flask
import logging
import sys

from DeviceManager import DeviceManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

manager = DeviceManager(logger)


app = flask.Flask(__name__)

@app.route("/devices/all")
def devices_all():
    return manager.getDevices()

@app.route("/devices/available")
def devices_available():
    return manager.getDevicesAvailable()

@app.route("/devices/buses/<device>")
def devices_bus(device):
    if device not in manager.devs:
        return "", 400
    
    return manager.devs[device].exported_devices, 200

@app.route("/devices/reserve/<device>", methods=["PUT", "DELETE"])
def devices_reserve_put(device):
    if flask.request.method == "PUT":
        if device not in manager.devs:
            return "", 403
        
        res = manager.devs[device].reserve()
        return "", 200 if res else 403
    else:
        if device not in manager.devs:
            return "", 403
        
        res = manager.devs[device].unreserve()
        return "", 200 if res else 403

app.run()

