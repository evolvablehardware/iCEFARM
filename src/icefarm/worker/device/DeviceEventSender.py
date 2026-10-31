from __future__ import annotations
from logging import Logger

from icefarm.utils import EventSender, BaseEvent

class DeviceInitialized(BaseEvent, register_args=["serial"]):
    def __init__(self, serial):
        super().__init__()
        self.serial = serial

class DeviceReservationEnd(BaseEvent, register_args=["serial"]):
    def __init__(self, serial):
        super().__init__()
        self.serial = serial

class DeviceFailure(BaseEvent, register_args=["serial"]):
    def __init__(self, serial):
        super().__init__()
        self.serial = serial

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
        if not self.event_sender.sendSerial(events):
            self.logger.error(f"failed to sent events: {events}")
            return False

        return True

    def sendDeviceInitialized(self):
        return self.event_sender.sendSerial(DeviceInitialized(self.serial))

    def sendDeviceReservationEnd(self) -> bool:
        """Sends a reservation end event for serial."""
        return self.event_sender.sendSerial(DeviceReservationEnd(self.serial))

    def sendDeviceFailure(self) -> bool:
        """Sends a failure event for serial."""
        return self.event_sender.sendSerial(DeviceFailure(self.serial))
