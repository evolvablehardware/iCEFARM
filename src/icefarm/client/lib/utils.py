from logging import Logger
from icefarm.client.lib import AbstractEventHandler, register

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
    """Logs received events."""
    def __init__(self, event_server, logger: Logger):
        super().__init__(event_server)
        self.logger = logger

    def handleEvent(self, event):
        self.logger.info(f"Received event: {event.event} serial: {event.serial} contents: {event.contents}")

class ReservationExtender(AbstractEventHandler):
    def __init__(self, event_server, client, logger: Logger):
        super().__init__(event_server)
        self.client = client
        self.logger = logger

    def handleReservationEndingSoon(self, serial: str):
        if self.client.extend[serial]:
            self.logger.info(f"refreshed reservation of {serial}")
        else:
            self.logger.error(f"failed to refresh reservation of device {serial}")
