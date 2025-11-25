from logging import Logger, LoggerAdapter
import threading

from worker.WorkerDatabase import WorkerDatabase
from utils.NotificationSender import NotificationSender

DEFAULT_FIRMWARE_PATH = ""
class DeviceLogger(LoggerAdapter):
    def __init__(self, logger, serial):
        super().__init__(logger, extra={"serial": serial})

    def process(self, msg, kwargs):
        return f"[{self.extra["serial"]}] {msg}"

class Device:
    def __init__(self, serial: str, logger: Logger, database: WorkerDatabase, notif: NotificationSender):
        self.serial = serial
        self.logger = DeviceLogger(logger, serial)
        self.database = database
        self.notif = notif
        self.device = None #TODO flash

        self.device_lock = threading.Lock()

    def handleDeviceEvent(self, action, dev):
        with self.device_lock:
            if not self.device:
                return

            device = self.device

        if action == "add":
            device.handleAdd(dev)
            return

        if action == "remove":
            device.handleRemove(dev)
            return

        self.getLogger().warning(f"unhandled device action: {action}")

    def handleUnreserve(self):
        # TODO
        self.getDatabase().updateDeviceStatus(self.getSerial(), "flashing_default")

    def handleEvent(self, event, json):
        self.device.handleEvent(event, json)

    def switch(self, state_factory):
        with self.device_lock:
            if self.device:
                self.device.handleExit()
            self.device = state_factory()

    def getSerial(self) -> str:
        return self.serial

    def getLogger(self) -> Logger:
        return self.logger

    def getDatabase(self) -> WorkerDatabase:
        return self.database

    def getNotif(self) -> NotificationSender:
        return self.notif
