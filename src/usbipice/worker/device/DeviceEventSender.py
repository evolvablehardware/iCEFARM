from logging import Logger
import json

from usbipice.worker import EventSender

class DeviceEventSender:
    """Allows for sending event notifications to client's event server, as well as sending 
    instructions to worker's servers.."""
    def __init__(self, event_sender: EventSender, serial: str, logger: Logger):
        self.event_sender = event_sender
        self.serial = serial
        self.logger = logger

    def sendDeviceEvent(self, contents: dict) -> bool:
        contents["serial"] = self.serial
        contents = {
            "serial": self.serial,
            "contents": contents
        }

        try:
            data = json.dumps(contents)
        except Exception:
            self.logger.error("failed to stringify json")
            return False

        self.event_sender.send(self.serial, data)
        return True

    def sendDeviceInitialized(self):
        return self.sendDeviceEvent({"event": "initialized"})

    def sendDeviceReservationEnd(self) -> bool:
        """Sends a reservation end event for serial."""
        return self.sendDeviceEvent({"event": "reservation end"})

    def sendDeviceFailure(self) -> bool:
        """Sends a failure event for serial."""
        return self.sendDeviceEvent({"event": "failure"})
