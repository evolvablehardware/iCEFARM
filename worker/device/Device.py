from __future__ import annotations
import os
import shutil
from logging import Logger, LoggerAdapter
import threading

from worker.WorkerDatabase import WorkerDatabase
from worker.device.state import FlashState
from worker.device.state import TestState
from worker.device.state import UsbipState
from utils.NotificationSender import NotificationSender

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from worker.device.state import AbstractState

DEFAULT_FIRMWARE_PATH = "worker/firmware/build/default_firmware.uf2"
WORKER_MEDIA = "worker_media"
class DeviceLogger(LoggerAdapter):
    def __init__(self, logger, serial):
        super().__init__(logger, extra={"serial": serial})

    def process(self, msg, kwargs):
        return f"[{self.extra["serial"]}] {msg}", kwargs

class Device:
    def __init__(self, serial: str, logger: Logger, database: WorkerDatabase, notif: NotificationSender):
        self.serial = serial
        self.logger = DeviceLogger(logger, serial)
        self.database = database
        self.notif = notif
        self.device: AbstractState = None
        self.device_lock = threading.Lock()

        if not os.path.isdir(WORKER_MEDIA):
            os.mkdir(WORKER_MEDIA)

        self.path = os.path.join(WORKER_MEDIA, self.serial)
        if not os.path.isdir(self.path):
            os.mkdir(self.path)

        self.firmware_path = os.path.join(self.path, "firmware")
        if not os.path.isdir(self.firmware_path):
            os.mkdir(self.firmware_path)
        self.firmware_path = os.path.join(self.firmware_path, "firmware.uf2")

        self.mount_path = os.path.join(self.path, "mount")
        if not os.path.isdir(self.mount_path):
            os.mkdir(self.mount_path)

        self.__flashDefault()

    def __flashDefault(self):
        shutil.copyfile(DEFAULT_FIRMWARE_PATH, self.firmware_path)
        self.getDatabase().updateDeviceStatus(self.getSerial(), "flashing_default")
        self.switch(lambda : FlashState(self, self.mount_path, self.firmware_path, lambda : TestState(self)))

    def reserveUsbip(self):
        self.switch(lambda : UsbipState(self))

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
        self.__flashDefault()

    def handleRequest(self, event, json):
        return self.device.handleRequest(event, json)

    def handleExit(self):
        with self.device_lock:
            if self.device:
                self.device.handleExit()

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
