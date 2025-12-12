from logging import LoggerAdapter

import psycopg

from usbipice.worker import Config
from usbipice.utils import Database, DeviceState

class WorkerDataBaseLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[WorkerDatabase] {msg}", kwargs

class WorkerDatabase(Database):
    """Provides access to database operations related to the worker process."""
    def __init__(self, config: Config, logger):
        super().__init__(config.getDatabase())
        self.worker_name = config.getName()
        self.logger = WorkerDataBaseLogger(logger)

        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL addWorker(%s::varchar(255), %s::inet, %s::int)", (self.worker_name, config.getVirtualIp(), config.getVirtualPort()))
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
