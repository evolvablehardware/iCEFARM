from __future__ import annotations
from pathlib import Path
from logging import Logger, LoggerAdapter
import threading

from usbipice.worker.device import DeviceEventSender
from usbipice.worker.device.state.core import FlashState, TestState
from usbipice.worker.device.state.reservable import get_reservation_state_fac

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from usbipice.worker import WorkerDatabase, Config, EventSender
    from usbipice.worker.device import DeviceManager
    from usbipice.worker.device.state.core import AbstractState

# TODO add this to config
WORKER_MEDIA = "worker_media"

class DeviceLogger(LoggerAdapter):
    def __init__(self, logger, serial):
        super().__init__(logger, extra={"serial": serial})

    def process(self, msg, kwargs):
        return f"[{self.extra['serial']}] {msg}", kwargs

class Device:
    def __init__(self, serial: str, manager: DeviceManager, event_sender: EventSender, database: WorkerDatabase, logger: Logger):
        self.serial = serial
        self.manager = manager
        self.database = database
        self.logger = DeviceLogger(logger, self.serial)
        self.device_event_sender = DeviceEventSender(event_sender, self.serial, self.logger)

        self.device: AbstractState = None
        self.device_lock = threading.RLock()

        self.path = Path(WORKER_MEDIA).joinpath(self.getSerial())

        self.path.joinpath("mount").mkdir(parents=True, exist_ok=True)
        self.path.joinpath("media").mkdir(exist_ok=True)

        self.__flashDefault()

    def __flashDefault(self):
        self.getDatabase().updateDeviceStatus(self.getSerial(), "flashing_default")
        self.switch(lambda : FlashState(self, self.getConfig().getDefaultFirmwarePath(), lambda : TestState(self), timeout=60))

    def handleDeviceEvent(self, action, dev):
        with self.device_lock:
            if not self.device:
                return

            with self.device.getSwitchLock():
                self.logger.debug(f"device {dev["DEVPATH"]}")

                if action == "add":
                    self.device.handleAdd(dev)
                    return

                if action == "remove":
                    self.device.handleRemove(dev)
                    return

                self.getLogger().warning(f"unhandled device action: {action}")

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
        with self.device_lock:
            self.device.handleRequest(event, json)

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
            self.device.start()

    def getSerial(self) -> str:
        return self.serial

    def getLogger(self) -> Logger:
        return self.logger

    def getDatabase(self) -> WorkerDatabase:
        return self.database

    def getEventSender(self) -> DeviceEventSender:
        return self.device_event_sender

    def getManager(self) -> DeviceManager:
        return self.manager

    def getConfig(self) -> Config:
        return self.getManager().getConfig()

    def getPath(self) -> Path:
        return self.path

    def getMountPath(self) -> str:
        return str(self.path.joinpath("mount"))

    def getMediaPath(self) -> Path:
        return self.path.joinpath("media")
