from logging import LoggerAdapter

from icefarm.utils import (
    EventSender,
    DeviceReservationEnd,
    DeviceFailure,
    DeviceReservationEndingSoon,
    DevicesAvailable,
)

class ControlEventSenderLogger(LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return f"[ControlEventSender] {msg}", kwargs

# TODO this can probably be removed now?
class ControlEventSender(EventSender):
    def __init__(self, socketio, dburl, logger):
        super().__init__(socketio, dburl, ControlEventSenderLogger(logger))

    def sendDeviceReservationEnd(self, serial: str, client_id: str) -> bool:
        """Sends a reservation end event for serial."""
        if not self.sendClientJson(serial, client_id, DeviceReservationEnd(serial)):
            self.logger.warning(f"failed to send reservation end to {client_id} for device {serial}")
            return False

        self.logger.info(f"sent reservation end to {client_id} for device {serial}")
        return True

    def sendDeviceFailure(self, serial: str, client_id: str) -> bool:
        """Sends a failure event for serial."""
        if not self.sendClientJson(serial, client_id, DeviceFailure(serial)):
            self.logger.warning(f"failed to send device failure to {client_id} for device {serial}")
            return False

        self.logger.info(f"sent device failure to {client_id} for device {serial}")
        return True

    def sendDeviceReservationEndingSoon(self, serial: str) -> bool:
        """Sends a reservation ending soon event for serial."""
        if not self.sendSerialJson(serial, DeviceReservationEndingSoon(serial)):
            self.logger.warning(f"failed to send reservation ending soon to device {serial}")
            return False

        self.logger.info(f"sent reservation ending soon to device {serial}")
        return True

    def sendDevicesAvailableChange(self, amount: int) -> bool:
        if not self.sendAllJson(DevicesAvailable(amount)):
            self.logger.warning(f"failed to send devices available change: {amount}")
            return False

        self.logger.debug(f"sent notification for devices available change: {amount}")
        return True

