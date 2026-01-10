from __future__ import annotations
from threading import Lock
from logging import Logger

import requests

class ConnectionInfo:
    """Database for information required to establish and maintain usbip connections."""
    def __init__(self, ip: str, server_port: str):
        self.ip = ip
        self.server_port = server_port

    def __eq__(self, value):
        return self.ip == value.ip and self.server_port == value.ip

    def url(self):
        return f"http://{self.ip}:{self.server_port}"

class BaseAPI:
    """Provides an an abstraction over control server http endpoints and tracks reserved devices."""
    def __init__(self, url: str, client_name: str, logger: Logger):
        self.url = url
        self.name = client_name
        self.connection_info = {}
        self.lock = Lock()
        self.logger = logger

    def addSerial(self, serial, conn_info: ConnectionInfo):
        with self.lock:
            self.connection_info[serial] = conn_info

    def removeSerial(self, serial: str) -> bool:
        """Manually removes a device. Should be called after reservations end or
        devices fail. Returns whether it was successful."""
        with self.lock:
            if serial in self.connection_info:
                del self.connection_info[serial]
                return True

        return False

    def getSerials(self) -> list[str]:
        """Returns tracked serials."""
        with self.lock:
            return list(self.connection_info.keys())

    def getConnectionInfo(self, serial: str) -> ConnectionInfo:
        """Returns connection information associated with a serial."""
        with self.lock:
            return self.connection_info.get(serial)

    def usingConnection(self, info: ConnectionInfo):
        """Returns whether a connection is currently in use by a device."""
        with self.lock:
            return info in self.connection_info.values()

    def request(self, url: str, endpoint: str, json: dict, files=None) -> dict:
        """Sends a GET to url/endpoint with json. If files is specified, the data
        is instead sent as a multipart forum."""
        try:
            if files:
                res = requests.get(f"{url}/{endpoint}", data=json, files=files, timeout=20)
            else:
                res = requests.get(f"{url}/{endpoint}", json=json, timeout=20)

            if res.status_code != 200:
                self.logger.error(f"failed to GET /{endpoint}")
                return False

            return res.json()
        except Exception as e:
            self.logger.error(f"Exception during GET /{endpoint}: {e}")
            return False

    def requestControl(self, endpoint: str, json: dict) -> dict:
        """Sends a GET request to the specified endpoint of the control server with the specified json. Returns json of the response.
        Returns False on error."""
        return self.request(self.url, endpoint, json)

    def requestWorker(self, serial, endpoint, json, files={}) -> dict:
        conn_info = self.getConnectionInfo(serial)

        if not conn_info:
            return False

        return self.request(conn_info.url(), endpoint, json, files=files)

    def reserve(self, amount: int, kind: str, args: dict) -> dict:
        """Reserves amount devices with subscription_url as a event server.
        Returns successful reservations as a dict of serial -> bus"""
        json = {
            "amount": amount,
            "name": self.name,
            "kind": kind,
            "args": args
        }

        data = self.requestControl("reserve", json)

        if data is False:
            return False

        out = []

        for row in data:
            serial = row["serial"]
            info = ConnectionInfo(row["ip"], row["serverport"])
            self.addSerial(serial, info)

            out.append(serial)

        return out

    def extend(self, serials: list[str]) -> list[str]:
        """Extends the reservation on serials for by hour. The serials must be reserved under the client's name.
        Returns the serials that were extended."""
        return self.requestControl("extend", {
            "name": self.name,
            "serials": serials
        })

    def extendAll(self) -> list[str]:
        """Extends all reservations by the under the client's name for by hour. Returns the serials that were extended."""
        return self.requestControl("extendall", {
            "name": self.name
        })

    def end(self, serials: list[str]) -> list[str]:
        """Ends the reservation on serials. The serials must be reserved under the client's name. Returns the serials of reservations
        that were ended."""
        if not isinstance(serials, list):
            serials = list(serials)

        json = self.requestControl("end", {
            "name": self.name,
            "serials": serials
        })

        if json is False:
            return False

        for serial in json:
            self.removeSerial(serial)

        return json

    def endAll(self) -> list[str]:
        """Ends all reservations under the client's name. Returns the serials of reservations that were ended.."""
        json = self.requestControl("endall", {
            "name": self.name
        })

        if json is False:
            return False

        for serial in json:
            self.removeSerial(serial)

        return json
