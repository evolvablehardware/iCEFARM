from logging import Logger

from usbipice.client.lib import EventServer, BaseAPI
from usbipice.client.lib.default import DefaultBaseEventHandler

class DefaultEventHandler(DefaultBaseEventHandler):
    def __init__(self, event_server: EventServer, api: BaseAPI, logger: Logger):
        super().__init__(event_server)
        self.api = api
        self.logger = logger

    def handleReservationEndingSoon(self, serial: str):
        """Attempts to extend the reservation of the device."""
        if self.api.extend([serial]):
            self.logger.info(f"refreshed reservation of {serial}")
        else:
            self.logger.error(f"failed to refresh reservation of {serial}")

    def handleReservationEnd(self, serial: str):
        """Prints a notification and removes the device from the client"""
        self.logger.info(f"reservation for device {serial} ended")
        self.api.removeSerial(serial)

    def handleFailure(self, serial: str):
        """Prints an error and removes the device from the client"""
        self.logger.error(f"device {serial} failed")
        self.api.removeSerial(serial)
