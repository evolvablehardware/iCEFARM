import requests
from requests_sse import EventSource
import fire
import os

# TODO make these configurable
DEFAULT_SERVER = "http://localhost:5000"

def validate(req):
    if not req.status_code == 200:
        raise Exception(f"error on server: {req.status_code}")

    return req.json()

def all(server=DEFAULT_SERVER):
    r = validate(requests.get(f"{server}/devices/all"))
    if not r:
        return "no devices connected"
    
    return r

def available(server=DEFAULT_SERVER):
    r = validate(requests.get(f"{server}/devices/available"))
    if not r:
        return "all devices reserved/none connected"
    
    return r

def bus(device, server=DEFAULT_SERVER):
    r = validate(requests.get(f"{server}/devices/bus/{device}"))
    if not r:
        return "no exported buses"

    return r

def reserve(device, server=DEFAULT_SERVER):
    r = validate(requests.get(f"{server}/devices/reserve/{device}"))
    return "success!"

def unreserve(device, server=DEFAULT_SERVER):
    r = validate(requests.get(f"{server}/devices/unreserve/{device}"))
    return "success!"

def flash(firmware, device, server=DEFAULT_SERVER, name="default_name"):
    if not os.path.isfile(firmware):
        return "error: file does not exist"
    
    devices = all(server=server)

    if device == "auto":
        if len(devices) != 1:
            return "error: can only use auto when target server has exactly one device"
        
        device = devices[0]
    
    if device not in devices:
        return "error: device not found"
    
    with open(firmware, "rb") as f:
        uf2 = f.read()

    with EventSource(f"{server}/devices/flash/{device}", data={"name": name}, files={"firmware": uf2}) as source:
        for event in source:
            data = event.data[1:-1]
            print(data)

            if data == "upload complete":
                break

fire.Fire()