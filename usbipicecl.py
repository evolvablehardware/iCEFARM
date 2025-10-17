import requests
from requests_sse import EventSource
import fire
import os
import uvicorn
import threading
import subprocess
import atexit

from clutils import *
from utils import getIp

DEFAULT_MANAGER_SERVER = "http://localhost:5000"
DEFAULT_DEVICE_IP= "localhost"

CLIENT_SERVER = ""

def connect(server=DEFAULT_MANAGER_SERVER, device_ip=DEFAULT_DEVICE_IP, device="auto", port=8080):
    """Reserve a device and connect to it with usbip. If a client server is set,
    it will register a callback to it and automatically reconnect if usbip gets disconnected.
    If a client server is not specified, it will run one and unreserve the device when the process
    is stopped.
    """
    if device == "auto":
        av = getAvailable(server)

        if av == False:
            return "failed to retrieve available devices"
        
        if not av:
            return "no devices available"
        
        device = av[0]
    
    if not CLIENT_SERVER:
        t = threading.Thread(target=lambda : uvicorn.run("client:app", host="0.0.0.0", port=port))
        t.start()
        r = sendReserve(device, server=server, callback=f"http://{getIp()}:{port}")
        atexit.register(lambda : sendUnreserve(device, server))
    else:
        r = sendReserve(device, server=server, callback=CLIENT_SERVER)
    
    if r == False:
        return f"failed to reserve device {device}"
    
    
    bus = getBus(device, server)

    if not bus:
        return f"failed to get bus from device {device}"
    
    subprocess.run(["sudo", "usbip", "attach", "-r", device_ip, "-b", bus])

    if t:
        t.join()

def all(server=DEFAULT_MANAGER_SERVER):
    """Get list of all devices - this includes ones that are reserved."""
    a = getAll(server)
    if a == False:
        return "request failed"
    
    return a

def available(server=DEFAULT_MANAGER_SERVER):
    """Get list of devices that are not reserved"""
    av = getAvailable(server)
    if av == False:
        return "request failed"
    
    if not av:
        return "no devices available/all devices reserved"
    
    return av

def bus(device, server=DEFAULT_MANAGER_SERVER):
    """Get busid for usage with usbip of a device"""

    b = getBus(device, server)

    if b == False:
        return "request failed"
    
    if not b:

        return "no exported buses"

    return b

def reserve(device, server=DEFAULT_MANAGER_SERVER):
    """Mark a device as reserved"""
    if sendReserve(device, server):
        return "success!"

    return "request failed"

def unreserve(device, server=DEFAULT_MANAGER_SERVER):
    """Mark a device as available"""
    if sendUnreserve(device, server):
        return "success!"
    
    return "request failed"

def flash(firmware, device, server=DEFAULT_MANAGER_SERVER, name="default_name"):
    """Flash firmware onto a device"""
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