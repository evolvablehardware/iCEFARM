from __future__ import annotations
from logging import LoggerAdapter
from importlib.metadata import version

import psycopg

from usbipice.utils import Database
from usbipice.worker.device.state.reservable import get_registered_reservables

import typing
if typing.TYPE_CHECKING:
    from usbipice.worker import Config
    from usbipice.utils import DeviceState

class WorkerDataBaseLogger(LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return f"[WorkerDatabase] {msg}", kwargs

# TODO use __execute
class WorkerDatabase(Database):
    """Provides access to database operations related to the worker process."""
    def __init__(self, config: Config, logger):
        super().__init__(config.libpg_string)
        self.worker_name = config.worker_name
        self.logger = WorkerDataBaseLogger(logger)

        usbipice_version = version("usbipice")
        reservables = get_registered_reservables()

        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL addWorker(%s::varchar(255), %s::varchar(255), %s::int, %s::varchar(255), %s::varchar(255)[])", (self.worker_name, config.virtual_ip, config.virtual_server_port, usbipice_version, reservables))
                    conn.commit()

        except Exception:
            logger.critical(f"Failed to add worker {self.worker_name}")
            raise Exception(f"Failed to add worker {self.worker_name}")


    def addDevice(self, deviceserial: str) -> bool:
        """Add a device to the database."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL addDevice(%s::varchar(255), %s::varchar(255))", (deviceserial, self.worker_name))
                    conn.commit()
        except Exception:
            self.logger.error(f"failed to add device {deviceserial}")
            return False

        return True

    def updateDeviceStatus(self, deviceserial: str, status: DeviceState) -> bool:
        """Updates the status field of a device."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL updateDeviceStatus(%s::varchar(255), %s::DeviceState)", (deviceserial, status))
                    conn.commit()
        except Exception:
            self.logger.error(f"failed to update device {deviceserial} to status {status}")
            return False

    def onExit(self):
        """Removes the worker and all related devices from the database."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM removeWorker(%s::varchar(255))", (self.worker_name,))
                    data = cur.fetchall()
        except Exception:
            self.logger.warning(f"failed to remove worker {self.worker_name} before exit")
            return
