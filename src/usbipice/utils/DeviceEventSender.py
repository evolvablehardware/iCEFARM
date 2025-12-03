from logging import Logger

import psycopg
import requests

from usbipice.worker import Config
from usbipice.utils import Database

class DeviceEventSender(Database):
    """Allows for sending event notifications to client's event server, as well as sending 
    instructions to worker's servers.."""
    def __init__(self, dburl: str, logger: Logger):
        super().__init__(dburl)
        self.logger = logger

    def getDeviceEventUrl(self, deviceserial: str) -> str:
        """Returns the event server url for a device, None if there is none, or False on error."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM getDeviceCallback(%s::varchar(255))", (deviceserial,))
                    data = cur.fetchall()
        except Exception:
            self.logger.warning(f"failed to get device callback for serial {deviceserial}")
            return False

        if not data:
            # no reservation
            return None

        return data[0][0]

    def sendDeviceEvent(self, deviceserial: str, contents: dict, url=None) -> bool:
        """Sends a GET request with json=contents to the event server of the device. 
        Returns whether successful. If url=None, the url is derived from the devices 
        current reservation."""
        if not url:
            url = self.getDeviceEventUrl(deviceserial)

        if not url:
            return False

        try:
            res = requests.get(url, json=contents, timeout=10)
            if res.status_code != 200:
                raise Exception

        except Exception:
            self.logger.warning(f"failed to send subscription update for {deviceserial} to {url}")
            return False

        self.logger.debug(f"sent subscription update for {deviceserial} to {url}")
        return True

    def sendDeviceInitialized(self, deviceserial: str, url=None):
        return self.sendDeviceEvent(deviceserial, {
            "event": "initialized"
        }, url)

    def sendDeviceDisconnect(self, serial: str, url=None) -> bool:
        """Sends a device disconnect event for serial."""
        return self.sendDeviceEvent(serial, {
            "event": "disconnect",
            "serial": serial
        }, url=url)

    def sendDeviceReservationEndingSoon(self, serial: str, url=None) -> bool:
        """Sends a reservation ending soon event for serial."""
        return self.sendDeviceEvent(serial, {
            "event": "reservation ending soon",
            "serial": serial
        }, url=url)

    def sendDeviceReservationEnd(self, serial: str, url=None) -> bool:
        """Sends a reservation end event for serial."""
        return self.sendDeviceEvent(serial, {
            "event": "reservation end",
            "serial": serial
        }, url=url)

    def sendDeviceFailure(self, serial: str, url=None) -> bool:
        """Sends a failure event for serial."""
        return self.sendDeviceEvent(serial, {
            "event": "failure",
            "serial": serial
        }, url=url)
