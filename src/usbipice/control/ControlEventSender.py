from logging import LoggerAdapter

from usbipice.worker import EventSender

class ControlEventSenderLogger(LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return f"[ControlEventSender] {msg}", kwargs

class ControlEventSender(EventSender):
    def __init__(self, socketio, dburl, logger):
        super().__init__(socketio, dburl, ControlEventSenderLogger(logger))

    def sendDeviceReservationEnd(self, serial: str, client_id: str) -> bool:
        """Sends a reservation end event for serial."""
        if not self.sendClientJson(serial, client_id, {
            "event": "reservation end",
        }):
            self.logger.warning(f"failed to send reservation end to {client_id} for device {serial}")

    def sendDeviceFailure(self, serial: str, client_id: str) -> bool:
        """Sends a failure event for serial."""
        if not self.sendClientJson(serial, client_id, {
            "event": "failure",
        }):
            self.logger.warning(f"failed to send device failure to {client_id} for device {serial}")

    def sendDeviceReservationEndingSoon(self, serial: str) -> bool:
        """Sends a reservation ending soon event for serial."""
        if not self.sendSerialJson(serial, {
            "event": "reservation ending soon",
        }):
            self.logger.warning(f"failed to send reservation ending soon to device {serial}")
