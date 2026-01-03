from __future__ import annotations
from logging import Logger, LoggerAdapter
import threading
import atexit

import pyudev

from usbipice.utils.dev import *
from usbipice.worker.device import Device

import typing
if typing.TYPE_CHECKING:
    from usbipice.worker import Config, EventSender, WorkerDatabase

class ManagerLogger(LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return f"[DeviceManager] {msg}", kwargs

class DeviceManager:
    """Tracks device events and routes them to their corresponding Device object. Also listens to kernel
    device events to identify usbip disconnects."""
    def __init__(self, event_sender: EventSender, database: WorkerDatabase, config: Config, logger: Logger):
        self.config: Config = config
        self.logger: Logger = ManagerLogger(logger)
        self.event_sender: EventSender = event_sender
        self.database = database

        atexit.register(self.onExit)

        self._devs: dict[str, Device] = {}
        self._dev_lock = threading.Lock()

        self.exiting: bool = False

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by("tty")
        monitor.filter_by("block")

        observer = pyudev.MonitorObserver(monitor, self.handleDevEvent, name="manager-userevents")
        observer.start()

        self.scan()

    def scan(self):
        """Trigger add events for devices that are already connected."""
        self.logger.info("Scanning for devices")
        context = pyudev.Context().list_devices()

        for dev in context:
            self.handleDevEvent("add", dev)

        self.logger.info("Finished scan")

    def handleDevEvent(self, action: str, dev: pyudev.Device):
        """Ensures that a device is related to pico2ice and reroutes the event to handleAddDevice or
        handleRemoveDevice."""
        if self.exiting:
            return

        if dev.properties.get("ID_VENDOR_ID") not in ["2e8a", "1209"]:
            return

        dev = dict(dev)

        serial = get_serial(dev)

        if not serial:
            return

        with self._dev_lock:
            device = self._devs.get(serial)

            if not device:
                self.database.addDevice(serial)
                device = Device(serial, self, self.event_sender, self.database, self.logger)
                self._devs[serial] = device

        thread = threading.Thread(target=lambda : device.handleDeviceEvent(action, dev), name="dev-event-handler")
        thread.start()

    def handleRequest(self, serial: str, event: str, contents: dict):
        with self._dev_lock:
            dev = self._devs.get(serial)

        if not dev:
            self.logger.warning(f"request for {event} on {serial} but device not found")
            return

        return dev.handleRequest(event, contents)

    def reserve(self, serial: str, kind: str, args: dict):
        with self._dev_lock:
            device = self._devs.get(serial)

        if not device:
            self.logger.error(f"device {serial} reserved but does not exist")
            return False

        return device.handleReserve(kind, args)

    def unreserve(self, serial: str):
        with self._dev_lock:
            dev = self._devs.get(serial)

        if not dev:
            return False

        return dev.handleUnreserve()

    def onExit(self):
        """Callback for cleanup on program exit"""
        with self._dev_lock:
            devs = list(self._devs.values())

        for dev in devs:
            dev.handleExit()

        self.database.onExit()
