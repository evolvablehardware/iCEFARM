from usbipice.client.lib import AbstractEventHandler, register

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
        that is not recoverable."""
