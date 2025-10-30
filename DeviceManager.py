import pyudev
import re
import os

from utils import *
from Device import Device

class DeviceManager:
    def __init__(self, database, logger, unbind_on_exit=True):
        self.logger = logger
        self.database = database
        self.devs = {}

        self.unbind_on_exit = unbind_on_exit

        if not os.path.isdir("media"):
            os.mkdir("media")
        
        if not os.path.isdir("firmware"):
            os.mkdir("firmware")

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, lambda x, y : self.handleDevEvent(x, y), name="dev-observer")
        observer.start()

        # need kernel events for detecting usbip disconnects
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context, source="kernel")
        monitor.filter_by("usb", device_type="usb_device")
        observer = pyudev.MonitorObserver(monitor, lambda x, y : self.handleKernelEvent(x, y), name="kernel-observer")
        observer.start()

        self.scan()
    
    def scan(self):
        """Trigger add events for devices that are already connected"""
        self.logger.info("Scanning for devices")
        context = pyudev.Context().list_devices()

        for dev in context:
            self.handleDevEvent("add", dev)
        self.logger.info("Finished scan")
    
    def handleDevEvent(self, action, dev):
        dev = dict(dev)
        devname = dev.get("DEVNAME")

        if not devname:
            return

        if not re.match("/dev/", devname) or re.match("/dev/bus/", devname):
            return

        id_model = dev.get("ID_MODEL")

        # TODO we should have a config file for this stuff
        if id_model != "RP2350" and id_model != 'pico-ice' and id_model != 'Pico':
            return 
        
        serial = dev.get("ID_SERIAL_SHORT")

        if not serial:
            return

        if action == "add":
            self.handleAddDevice(serial, dev)
        elif action == "remove":
            self.handleRemoveDevice(serial, dev)
        else:
            self.logger.warning(f"Unhandled action type {action} for {format_dev_file(dev)}")

    def handleAddDevice(self, serial, udevinfo):
        if serial not in self.devs:
            self.logger.info(f"Creating device with serial {serial}")
            self.devs[serial] = Device(serial, self.logger, self.database)

            if not self.database.addDevice(serial):
                del self.devs[serial]
                return

            self.devs[serial].startBootloaderMode()
        
        self.devs[serial].handleAddDevice(udevinfo)

    def handleRemoveDevice(self, serial, udevinfo):
        if serial not in self.devs:
            self.logger.warning(f"tried to remove dev file {format_dev_file(udevinfo)} but does not exist")
            return
        
        self.devs[serial].handleRemoveDevice(udevinfo)
    
    def handleKernelEvent(self, action, dev):
        # NOTE: This should only be used for detecting usbip disconnects
        if action != "remove":
            return
    
        devpath = dev.properties.get("DEVPATH")

        if not devpath:
            return
        
        busid = re.search("/([0-9]+-[0-9]+)$", devpath)

        if not busid:
            self.logger.error(f"Kernel event for remove {format_dev_file(dev)} but was unable to parse busid from devpath. Device may no longer be available through usbip.")
            return
        
        busid = busid.group(1)

        connected_buses = get_exported_buses()

        if connected_buses == False:
            self.logger.error("unable to list exported usbip buses - is usbipd running?")
            return

        if busid in connected_buses:
            self.logger.error(f"Kernel event for remove {format_dev_file(dev)} implies bus {busid} was disconnected but still exporting it through usbip")
            return
        
        self.handleUsbipDisconnect(busid)
    
    def handleUsbipDisconnect(self, busid):
        for dev in self.devs.values():
            if dev.exported_busid != busid:
                continue

            dev.handleUsbipDisconnect()
            self.logger.info(f"device {dev.serial} on bus {busid} disconnected while exporting usbip")
            return
        
        self.logger.warning(f"Bus {busid} was disconnected but no devices were exporting on that bus - this may be an unrelated usb device")
        
    def onExit(self):
        """Callback for cleanup on program exit"""
        self.logger.info("exiting...")
        if self.unbind_on_exit:
            # TODO use dev info
            buses = get_exported_buses()
            for bus in buses:
                usbip_unbind(bus)
                self.logger.info(f"unbound bus {bus}")

        self.database.onExit()
    


        
        
