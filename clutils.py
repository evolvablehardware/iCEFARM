import requests

def validate(req):
    if not req.status_code == 200:
        return False

    return req.json()

def getAll(server):
    return validate(requests.get(f"{server}/devices/all"))

def getAvailable(server):
    return validate(requests.get(f"{server}/devices/available"))

def getBus(device, server):
    return validate(requests.get(f"{server}/devices/bus/{device}"))

def sendReserve(device, server, callback=None):
    if callback:
       return validate(requests.get(f"{server}/devices/reserve/{device}", data={"callback":callback}))

    return validate(requests.get(f"{server}/devices/reserve/{device}"))

def sendUnreserve(device, server):
    return validate(requests.get(f"{server}/devices/unreserve/{device}"))

    
