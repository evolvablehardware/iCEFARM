from __future__ import annotations
from logging import Logger
import threading
from icefarm.client.lib import AbstractEventHandler, register

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from icefarm.client.lib import BaseAPI

class DefaultBaseEventHandler(AbstractEventHandler):
    @register("reservation ending soon", "serial")
    def handleReservationEndingSoon(self, serial: str):
        """Called when the reservation is almost finished."""

    @register("reservation end", "serial")
    def handleReservationEnd(self, serial: str):
        """Called when the reservation has ended."""

    @register("failure", "serial")
    def handleFailure(self, serial: str):
        """Called when the device experiences an unexpected failure
        that is not recoverable.
        """

class LoggerEventHandler(AbstractEventHandler):
    """Logs all events received by the EventServer."""
    def __init__(self, event_server, logger: Logger):
        super().__init__(event_server)
        self.logger = logger

    def handleEvent(self, event):
        self.logger.info(f"Received event: {event.event} serial: {event.serial} contents: {event.contents}")

class ReservationExtender(AbstractEventHandler):
    """Automatically extends device reservations when they are nearing completion."""
    def __init__(self, event_server, client, logger: Logger):
        super().__init__(event_server)
        self.client = client
        self.logger = logger

    @register("reservation ending soon", "serial")
    def handleReservationEndingSoon(self, serial: str):
        if self.client.extend([serial]):
            self.logger.info(f"refreshed reservation of {serial}")
        else:
            self.logger.error(f"failed to refresh reservation of device {serial}")

class AvailabilityWaiter(AbstractEventHandler):
    """Allows the client to sleep until a desired about of devices are available."""
    def __init__(self, event_server, client: BaseAPI):
        super().__init__(event_server)
        self.client = client
        self.last_available = 0
        self.cv = threading.Condition()

    @register("devices_available", "amount")
    def available(self, amount):
        self.last_available = amount
        with self.cv:
            self.cv.notify_all()

    def waitForAmountAvailable(self, amount):
        """
        Returns once at least amount devices are available for reservation. Note that
        this does not guarantee this client will be able to reserve them, as another client
        might first.
        """
        if self.client.available() >= amount:
            return

        with self.cv:
            self.cv.wait_for(lambda : amount <= self.last_available)
