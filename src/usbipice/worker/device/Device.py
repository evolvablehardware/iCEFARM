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
        self.serial: str = serial
        self.manager: DeviceManager = manager
        self.database: WorkerDatabase = database
        self.logger: Logger = DeviceLogger(logger, self.serial)
        self.device_event_sender: DeviceEventSender = DeviceEventSender(event_sender, self.serial, self.logger)

        self._device: AbstractState = None
        self._device_lock = threading.RLock()

        self.path = Path(WORKER_MEDIA).joinpath(self.serial)

        self.path.joinpath("mount").mkdir(parents=True, exist_ok=True)
        self.path.joinpath("media").mkdir(exist_ok=True)

        self.__flashDefault()

    def __flashDefault(self):
        self.database.updateDeviceStatus(self.serial, "flashing_default")
        self.switch(lambda : FlashState(self, self.config.default_firmware_path, lambda : TestState(self), timeout=60))

    def handleDeviceEvent(self, action, dev):
        with self._device_lock:
            if not self._device:
                return

            with self._device.switching_lock:
                self.logger.debug(f"device {dev["DEVPATH"]}")

                if action == "add":
                    self._device.handleAdd(dev)
                    return

                if action == "remove":
                    self._device.handleRemove(dev)
                    return

                self.logger.warning(f"unhandled device action: {action}")

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
        with self._device_lock:
            self._device.handleRequest(event, json)

    def handleExit(self):
        with self._device_lock:
            if self._device:
                self._device.handleExit()

    def reboot(self):
        self.logger.info("rebooting")
        with self._device_lock:
            if self._device:
                self._device.reboot()

    def switch(self, state_factory):
        with self._device_lock:
            if self._device:
                self._device.handleExit()
            device = state_factory()
            self._device = device
            self._device.start()

    @property
    def config(self) -> Config:
        return self.manager.config

    @property
    def mount_path(self) -> str:
        return self.path.joinpath("mount")

    @property
    def media_path(self) -> Path:
        return self.path.joinpath("media")
