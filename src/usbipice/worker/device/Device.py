from __future__ import annotations
from pathlib import Path
from logging import Logger, LoggerAdapter
import threading

from usbipice.worker import WorkerDatabase
from usbipice.worker.device import DeviceEventSender
from usbipice.worker.device.state.core import FlashState, TestState
from usbipice.worker.device.state.reservable import get_reservation_state_fac

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from usbipice.worker.device.state.core import AbstractState
    from usbipice.worker.device import DeviceManager

DEFAULT_FIRMWARE_PATH = "src/usbipice/worker/firmware/build/default_firmware.uf2"
WORKER_MEDIA = "worker_media"
class DeviceLogger(LoggerAdapter):
    def __init__(self, logger, serial):
        super().__init__(logger, extra={"serial": serial})

    def process(self, msg, kwargs):
        return f"[{self.extra["serial"]}] {msg}", kwargs

class Device:
    def __init__(self, serial: str, logger: Logger, database: WorkerDatabase, notif: DeviceEventSender, manager: DeviceManager):
        self.serial = serial
        self.logger = logger
        self.database = database
        self.notif = notif
        self.device: AbstractState = None
        self.device_lock = threading.Lock()
        self.manager = manager

        self.path = Path(WORKER_MEDIA).joinpath(self.getSerial())

        self.path.joinpath("mount").mkdir(parents=True, exist_ok=True)
        self.path.joinpath("media").mkdir(exist_ok=True)

        self.__flashDefault()

    def __flashDefault(self):
        self.getDatabase().updateDeviceStatus(self.getSerial(), "flashing_default")
        self.switch(lambda : FlashState(self, DEFAULT_FIRMWARE_PATH, lambda : TestState(self)))

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

        # TODO logger adapter?
        self.getLogger().warning(f"[{self.serial}] unhandled device action: {action}")

    def handleReserve(self, kind, args):
        fn = get_reservation_state_fac(self, kind, args)

        if not fn:
            return False

        self.switch(fn)
        return True

    def handleUnreserve(self):
        self.__flashDefault()
        return True

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
            device = state_factory()
            self.device = device

        device.start()

    def getSerial(self) -> str:
        return self.serial

    def getLogger(self) -> Logger:
        return self.logger

    def getDatabase(self) -> WorkerDatabase:
        return self.database

    def getNotif(self) -> DeviceEventSender:
        return self.notif

    def getManager(self) -> DeviceManager:
        return self.manager

    def getPath(self) -> Path:
        return self.path

    def getMountPath(self) -> str:
        return str(self.path.joinpath("mount"))

    def getMediaPath(self) -> Path:
        return self.path.joinpath("media")
