from __future__ import annotations
from logging import LoggerAdapter
from importlib.metadata import version
import threading

from icefarm.utils import Database
from icefarm.worker.device.state.reservable import get_registered_reservables

import typing
if typing.TYPE_CHECKING:
    from icefarm.worker import Config
    from icefarm.utils import DeviceStatus

class WorkerDataBaseLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[WorkerDatabase] {msg}", kwargs

class WorkerDatabase(Database):
    # TODO use Database.exec
    """Provides access to database operations related to the worker process."""
    def __init__(self, config: Config, logger):
        super().__init__(config.libpg_string)
        self.worker_name = config.worker_name
        self.logger = WorkerDataBaseLogger(logger)
        self.cv = threading.Condition()

        usbipice_version = version("icefarm")
        reservables = get_registered_reservables()

        args = (self.worker_name, config.virtual_ip, config.virtual_server_port, usbipice_version, reservables)
        if not self.execute("CALL add_worker(%s::varchar(255), %s::varchar(255), %s::int, %s::varchar(255), %s::varchar(255)[])", args):
            raise Exception(f"Failed to add worker {self.worker_name}")

    def addDevice(self, deviceserial: str) -> bool:
        """Add a device to the database."""
        if not self.execute("CALL add_device(%s::varchar(255), %s::varchar(255))", (deviceserial, self.worker_name)):
            self.logger.error(f"failed to add device {deviceserial}")
            return False

        return True

    def updateDeviceStatus(self, deviceserial: str, status: DeviceStatus) -> bool:
        """Updates the status field of a device."""
        if not self.execute("CALL update_device_status(%s::varchar(255), %s::devicestatus)", (deviceserial, status)):
            self.logger.error(f"failed to update device {deviceserial} to status {status}")
            return False

        return True

    def enableShutDown(self):
        if not self.execute("CALL shutdown_worker(%s::varchar(255))", (self.worker_name,)):
            self.logger.error("Failed to enable shut down mode")
            return False

        return True

    def hasReservations(self):
        if not (data := self.execute("SELECT * FROM has_reservations(%s::varchar(255))", (self.worker_name,))):
            self.logger.error("Failed to check for reservations")
            return None

        return data[0][0]

    def handleReservationChange(self):
        with self.cv:
            self.cv.notify_all()

    def waitUntilNoReservations(self):
        if self.hasReservations():
            with self.cv:
                self.cv.wait_for(lambda : not self.hasReservations())

    def onExit(self):
        """Removes the worker and all related devices from the database."""
        if not self.execute("SELECT * FROM remove_worker(%s::varchar(255))", (self.worker_name,)):
            self.logger.warning(f"failed to remove worker {self.worker_name} before exit")
