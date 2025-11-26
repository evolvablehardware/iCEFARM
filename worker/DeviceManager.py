import os
from logging import Logger

import pyudev

from utils.NotificationSender import NotificationSender
from utils.dev import *

from worker.WorkerDatabase import WorkerDatabase
from worker.device import Device

class DeviceManager:
    """Tracks device events and routes them to their corresponding Device object. Also listens to kernel
    device events to identify usbip disconnects."""
    def __init__(self, database: WorkerDatabase, notif: NotificationSender, logger: Logger, unbind_on_exit: bool=True):
        self.logger = logger
        self.notif = notif
        self.database = database
        self.devs = {}

        self.unbind_on_exit = unbind_on_exit
        self.exiting = False

        if not os.path.isdir("media"):
            os.mkdir("media")

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
            self.devs[serial] = Device(serial, self.logger, self.database, self.notif)

        self.devs[serial].handleDeviceEvent(action, dev)

    def handleRequest(self, serial, event, json):
        dev = self.devs.get(serial)

        if not dev:
            self.logger.warning(f"request for {event} on {serial} but device not found")
            return False

        return dev.handleRequest(event, json)

    def reserve(self, serial):
        device = self.devs.get(serial)

        if not device:
            self.logger.error(f"device {serial} reserved but does not exist")

        device.reserveUsbip()

    def unreserve(self, device: pyudev.Device):
        dev = self.devs.get(device)
        if not dev:
            return False

        dev.handleUnreserve()

    def onExit(self):
        """Callback for cleanup on program exit"""
        for dev in self.devs.values():
            dev.handleExit()
