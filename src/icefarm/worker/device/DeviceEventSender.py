from __future__ import annotations
from logging import Logger

from icefarm.utils import BaseEvent
from icefarm.utils import (
    EventSender,
    DeviceInitialized,
    DeviceReservationEnd,
    DeviceFailure,
)

# TODO this can probably be removed now
class DeviceEventSender:
    """Allows for sending event notifications to client's event server, as well as sending
    instructions to worker's servers.."""
    def __init__(self, event_sender: EventSender, serial: str, logger: Logger):
        self.event_sender = event_sender
        self.serial = serial
        self.logger = logger

    def sendDeviceEvent(self, event: BaseEvent) -> bool:
        return self.sendDeviceEvents([event])

    def sendDeviceEvents(self, events: list[BaseEvent]) -> bool:
        if not self.event_sender.sendSerialJson(self.serial, events):
            self.logger.error(f"failed to send events: {events}")
            return False

        return True

    def sendDeviceInitialized(self) -> bool:
        return self.sendDeviceEvent(DeviceInitialized(self.serial))

    def sendDeviceReservationEnd(self) -> bool:
        """Sends a reservation end event for serial."""
        return self.sendDeviceEvent(DeviceReservationEnd(self.serial))

    def sendDeviceFailure(self) -> bool:
        """Sends a failure event for serial."""
        return self.sendDeviceEvent(DeviceFailure(self.serial))
