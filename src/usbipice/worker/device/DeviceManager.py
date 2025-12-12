from logging import Logger, LoggerAdapter
import threading
import atexit
import json

import pyudev

from usbipice.utils.dev import *

from usbipice.worker import WorkerDatabase, Config, EventSender
from usbipice.worker.device import Device

class ManagerLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[DeviceManager] {msg}", kwargs

class DeviceManager:
    """Tracks device events and routes them to their corresponding Device object. Also listens to kernel
    device events to identify usbip disconnects."""
    def __init__(self, event_sender: EventSender, config: Config, logger: Logger):
        self.config = config
        self.logger = ManagerLogger(logger)
        self.event_sender = event_sender
        self.database = WorkerDatabase(config, self.logger)

        atexit.register(lambda : self.onExit())

        self.devs: dict[str, Device] = {}
        self.dev_lock = threading.Lock()

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

        with self.dev_lock:
            device = self.devs.get(serial)

            if not device:
                self.database.addDevice(serial)
                device = Device(serial, self, self.event_sender, self.database, self.logger)
                self.devs[serial] = device

        device.handleDeviceEvent(action, dev)

    def handleRequest(self, data: dict):
        try:
            contents = json.loads(data)
        except Exception:
            return False

        serial = contents.get("serial")
        event = contents.get("event")
        if not serial or not event:
            return

        dev = self.devs.get(serial)

        if not dev:
            self.logger.warning(f"request for {event} on {serial} but device not found")
            return

        return dev.handleRequest(event, contents)

    def reserve(self, data: dict):
        serial = data.get("serial")
        kind = data.get("kind")
        args = data.get("args")

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
