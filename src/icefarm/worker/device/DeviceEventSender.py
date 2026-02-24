from __future__ import annotations
from logging import Logger

from icefarm.utils import EventSender

class DeviceEventSender:
    """Allows for sending event notifications to client's event server, as well as sending
    instructions to worker's servers.."""
    def __init__(self, event_sender: EventSender, serial: str, logger: Logger):
        self.event_sender = event_sender
        self.serial = serial
        self.logger = logger

    def sendDeviceEvent(self, event: str, contents: dict) -> bool:
        """Sends a event with contents. Note that during serialization, the *event* key of
        contents is replaced. Do not use this key."""
        contents["event"] = event
        if not self.event_sender.sendSerialJson(self.serial, contents):
            self.logger.error("failed to send event")
            return False

        return True

    def sendDeviceInitialized(self):
        return self.sendDeviceEvent("initialized", {})

    def sendDeviceReservationEnd(self) -> bool:
        """Sends a reservation end event for serial."""
        return self.sendDeviceEvent("reservation end", {})

    def sendDeviceFailure(self) -> bool:
        """Sends a failure event for serial."""
        return self.sendDeviceEvent("failure", {})
