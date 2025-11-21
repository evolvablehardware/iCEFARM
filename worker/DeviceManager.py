import os
from logging import Logger

import pyudev

from utils.NotificationSender import NotificationSender
from utils.dev import *
from utils.usbip import get_exported_buses, usbip_unbind
from utils.utils import *

from worker.WorkerDatabase import WorkerDatabase
from worker.Device import Device

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

        self.disconnectAll()

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, lambda x, y : self.handleDevEvent(x, y), name="manager-userevents")
        observer.start()

        # need kernel events for detecting usbip disconnects
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context, source="kernel")
        monitor.filter_by("usb", device_type="usb_device")
        observer = pyudev.MonitorObserver(monitor, lambda x, y : self.handleKernelEvent(x, y), name="manager-kernelevents")
        observer.start()

        self.scan()

    def disconnectAll(self):
        """Disconnects all devices from usbip."""
        buses = get_exported_buses()
        if not buses:
            return

        for bus in buses:
            usbip_unbind(bus)
            self.logger.info(f"Unbound preexisting bound bus {bus}")

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

        if action == "add":
            self.handleAddDevice(serial, dev)
        elif action == "remove":
            self.handleRemoveDevice(serial, dev)
        else:
            self.logger.warning(f"Unhandled action type {action} for {format_dev_file(dev)}")

    def handleAddDevice(self, serial: str, udevinfo: pyudev.Device):
        """Reroutes add event to corresponding Device object."""
        if serial not in self.devs:
            self.logger.info(f"Creating device with serial {serial}")
            self.devs[serial] = Device(serial, self.logger, self.database, self.notif)

            if not self.database.addDevice(serial):
                del self.devs[serial]
                return

            self.devs[serial].startBootloaderMode()

        self.devs[serial].handleAddDevice(udevinfo)

    def handleRemoveDevice(self, serial: str, udevinfo: pyudev.Device):
        """Reroutes remove event to corresponding Device object."""
        if serial not in self.devs:
            self.logger.warning(f"tried to remove dev file {format_dev_file(udevinfo)} but does not exist")
            return

        self.devs[serial].handleRemoveDevice(udevinfo)

    def handleKernelEvent(self, action: str, dev: pyudev.Device):
        """Handles kernels events and detects whether an event is a usbip disconnect."""
        # NOTE: This should only be used for detecting usbip disconnects
        if action != "remove":
            return

        devpath = dev.properties.get("DEVPATH")

        if not devpath:
            return

        busid = get_busid(dict(dev))

        if not busid:
            self.logger.error(f"Kernel event for remove {format_dev_file(dev)} but was unable to parse busid from devpath. Device may no longer be available through usbip.")
            return

        connected_buses = get_exported_buses()

        if connected_buses is False:
            self.logger.error("unable to list exported usbip buses - is usbipd running?")
            return

        if busid in connected_buses:
            self.logger.error(f"Kernel event for remove {format_dev_file(dev)} implies bus {busid} was disconnected but still exporting it through usbip")
            return

        self.handleUsbipDisconnect(busid)

    def handleUsbipDisconnect(self, busid: str):
        """Reroutes usbip disconnect to its corresponding Device object."""
        for dev in self.devs.values():
            if dev.exported_busid != busid:
                continue

            dev.handleUsbipDisconnect()
            return

        self.logger.warning(f"Bus {busid} was disconnected but no devices were exporting on that bus - this may be an unrelated usb device")

    def unreserve(self, device: pyudev.Device):
        dev = self.devs.get(device)
        if not dev:
            return False

        # this also force disconnects any clients with expired reservations from usbip!
        dev.startBootloaderMode()
        self.database.updateDeviceStatus(device, "flashing_default")
        return True

    def unbind(self, serial: str):
        dev = self.devs.get(serial)

        if not dev:
            return False

        if not dev.exported_busid:
            return False

        return usbip_unbind(dev.exported_busid)

    def onExit(self):
        """Callback for cleanup on program exit"""
        self.logger.info("exiting...")
        self.exiting = True
        if self.unbind_on_exit:
            # TODO use dev info
            buses = get_exported_buses()
            for bus in buses:
                usbip_unbind(bus)
                self.logger.info(f"unbound bus {bus}")

        self.database.onExit()
