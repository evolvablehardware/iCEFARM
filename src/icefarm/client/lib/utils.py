from __future__ import annotations
from logging import Logger
import threading
from icefarm.utils import BaseEvent
from icefarm.client.lib import AbstractEventHandler, register
from icefarm.utils import (
    DeviceReservationEndingSoon,
    DeviceReservationEnd,
    DeviceFailure,
    DevicesAvailable,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from icefarm.client.lib import BaseAPI

class DefaultBaseEventHandler(AbstractEventHandler):
    @register(DeviceReservationEndingSoon)
    def handleReservationEndingSoon(self, event: DeviceReservationEndingSoon):
        """Called when the reservation is almost finished."""

    @register(DeviceReservationEnd)
    def handleReservationEnd(self, event: DeviceReservationEnd):
        """Called when the reservation has ended."""

    @register(DeviceFailure)
    def handleFailure(self, event: DeviceFailure):
        """Called when the device experiences an unexpected failure
        that is not recoverable.
        """

class LoggerEventHandler(AbstractEventHandler):
    """Logs all events received by the EventServer."""
    def __init__(self, event_server, logger: Logger):
        super().__init__(event_server)
        self.logger = logger

    def handleEvent(self, event: BaseEvent):
        self.logger.info(f"Received event: {event!r}")

class ReservationExtender(AbstractEventHandler):
    """Automatically extends device reservations when they are nearing completion."""
    def __init__(self, event_server, client, logger: Logger):
        super().__init__(event_server)
        self.client = client
        self.logger = logger

    @register(DeviceReservationEndingSoon)
    def handleReservationEndingSoon(self, event: DeviceReservationEndingSoon):
        if self.client.extend([event.serial]):
            self.logger.info(f"refreshed reservation of {event.serial}")
        else:
            self.logger.error(f"failed to refresh reservation of device {event.serial}")

class AvailabilityWaiter(AbstractEventHandler):
    """Allows the client to sleep until a desired about of devices are available."""
    def __init__(self, event_server, client: BaseAPI):
        super().__init__(event_server)
        self.client = client
        self.last_available = 0
        self.cv = threading.Condition()

    @register(DevicesAvailable)
    def available(self, event: DevicesAvailable):
        self.last_available = event.amount
        with self.cv:
            self.cv.notify_all()

    def waitForAmountAvailable(self, amount, timeout=None) -> bool:
        """
        Returns once at least amount devices are available for reservation. Returns False on timeout.
        Note that this does not guarantee this client will be able to reserve them, as another client
        might first.
        """
        if self.client.available() >= amount:
            return

        with self.cv:
            self.cv.wait_for(lambda : amount <= self.last_available, timeout=timeout)

            return amount <= self.last_available
