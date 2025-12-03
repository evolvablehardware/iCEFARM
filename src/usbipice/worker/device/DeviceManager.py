import os
from logging import Logger
import threading
import atexit

import pyudev

from usbipice.utils import DeviceEventSender
from usbipice.utils.dev import *

from usbipice.worker import WorkerDatabase, Config
from usbipice.worker.device import Device

class DeviceManager:
    """Tracks device events and routes them to their corresponding Device object. Also listens to kernel
    device events to identify usbip disconnects."""
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.notif = DeviceEventSender(config.getDatabase(), logger)
        self.database = WorkerDatabase(config, logger)

        atexit.register(lambda : self.onExit())

        self.devs: dict[str, Device] = {}

        self.kernel_lock = threading.Lock()
        self.kernel_add_subscribers: dict[str, Device] = {}
        self.kernel_remove_subscribers: dict[str, Device] = {}

        self.exiting = False

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, lambda x, y : self.handleDevEvent(x, y), name="manager-userevents")
        observer.start()

        self.scan()

    def scan(self):
        """Trigger add events for devices that are already connected."""
        self.logger.info("Scanning for devices")
        context = pyudev.Context().list_devices()

        for dev in context:
            dev = dict(dev)
            self.handleDevEvent("add", dev)
        self.logger.info("Finished scan")

    def handleDevEvent(self, action: str, dev: pyudev.Device):
        """Ensures that a device is related to pico2ice and reroutes the event to handleAddDevice or 
        handleRemoveDevice."""
        if self.exiting:
            return

        dev = dict(dev)

        serial = get_serial(dev)

        if not serial:
            return

        if serial not in self.devs:
            self.database.addDevice(serial)
            self.devs[serial] = Device(serial, self.logger, self.database, self.notif, self)

        self.devs[serial].handleDeviceEvent(action, dev)

    def handleRequest(self, json: dict):
        serial = json.get("serial")
        event = json.get("event")
        if not serial or not event:
            return

        dev = self.devs.get(serial)

        if not dev:
            self.logger.warning(f"request for {event} on {serial} but device not found")
            return

        return dev.handleRequest(event, json)

    def reserve(self, json: dict):
        serial = json.get("serial")
        kind = json.get("kind")
        args = json.get("args")

        if not isinstance(serial, str) or not isinstance(kind, str) or not isinstance(args, dict):
            return False

        device = self.devs.get(serial)

        if not device:
            self.logger.error(f"device {serial} reserved but does not exist")

        return device.handleReserve(kind, args)

    def unreserve(self, device: pyudev.Device):
        dev = self.devs.get(device)
        if not dev:
            return False

        return dev.handleUnreserve()

    def onExit(self):
        """Callback for cleanup on program exit"""
        for dev in self.devs.values():
            dev.handleExit()

        self.database.onExit()

    def getConfig(self) -> Config:
        return self.config
