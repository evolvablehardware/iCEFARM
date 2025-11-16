import os
from enum import Enum
from threading import Lock, Timer
from importlib.resources import files

from utils.dev import *
from utils.usbip import usbip_bind, usbip_unbind
from utils.utils import *

class Mode(Enum):
    NORMAL = 0
    BOOTLOADER = 1
    TEST = 2
    BROKEN = 3

class Device:
    def __init__(self, serial, logger, database, dev_files={}, bootloader_timeout_duration=30):
        self.serial = serial
        self.logger = logger
        self.dev_files = dev_files
        self.database = database

        self.mode = Mode.NORMAL
        self.bootloader_timeout_clock = None
        self.bootloader_timeout_duration = bootloader_timeout_duration

        self.exported_busid = None
        self.lock = Lock()
    
    def trackDevice(self, udevinfo):
        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} addDevice: no devname in udevinfo, ignoring")
            return False
        
        if identifier in self.dev_files.keys():
            self.logger.error(f"dev file {format_dev_file(udevinfo)} added but already exists, overwriting")
        
        self.dev_files[identifier] = udevinfo
        self.logger.info(f"added dev file {format_dev_file(udevinfo)}")

        return True
    
    def handleAddDevice(self, udevinfo, have_lock=False):
        # sometimes we want to manually trigger this 
        # when we already have the lock acquired
        if not have_lock:
            self.lock.acquire()

        match self.mode:
            case Mode.NORMAL:
                self.handleNormalAdd(udevinfo)
            case Mode.BOOTLOADER:
                self.handleBootloaderMode(udevinfo)
            case Mode.TEST:
                self.handleTestAdd(udevinfo)
        
        if not have_lock:
            self.lock.release()
    
    def handleNormalAdd(self, udevinfo):
        """Device action handler for NORMAL mode. Tracks and exports devs with usbip"""
        if not self.trackDevice(udevinfo):
            return

        busid = get_busid(udevinfo)

        binded = usbip_bind(busid)

        if not binded:
            self.logger.error(f"{format_dev_file(udevinfo)} failed to export usbip (bus {busid})")
            return

        self.logger.info(f"binded dev {format_dev_file(udevinfo)} on {busid}")

        self.exported_busid = busid
        self.database.updateDeviceBus(self.serial, busid)
        self.database.sendDeviceSubscription(self.serial, {
            "event": "export",
            "serial": self.serial,
            "bus": busid
        })

    def handleRemoveDevice(self, udevinfo):
        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier not in self.dev_files.keys():
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: dev file under major/minor does not exist, ignoring")
            return
        
        del self.dev_files[identifier]

        self.logger.info(f"removed dev file {format_dev_file(udevinfo)}")

    def startBootloaderMode(self):
        """Sets device to BOOTLOADER mode and retriggers dev events so they go through the 
        BOOTLOADER mode handler"""
        with self.lock:
            self.logger.info(f"reflashing device {self.serial} to default firmware")
            self.mode = Mode.BOOTLOADER

            if self.bootloader_timeout_clock:
                self.bootloader_timeout_clock.cancel()
                self.bootloader_timeout_clock = None
                self.logger.warning(f"Device {self.serial} bootloader timer already exists but entered mode, resetting timer")

            self.bootloader_timeout_clock = Timer(self.bootloader_timeout_duration, lambda : self.handleBootloaderTimeout())
            self.bootloader_timeout_clock.start()

            paths = list(self.dev_files.keys())

            for p in paths:
                file = self.dev_files[p]
                del self.dev_files[p]
                self.handleAddDevice(file, have_lock=True)

            if self.exported_busid:
                unbound = usbip_unbind(self.exported_busid)

                if unbound:
                    self.logger.info(f"unbound bus {self.exported_busid}")
                    self.exported_busid = None
                else:
                    self.logger.error(f"failed to unbind bus {self.exported_busid} (was the device disconnected?)")
                    self.database.updateDeviceStatus(self.serial, "broken")
                    return
            
            self.database.updateDeviceStatus(self.serial, "flashing_default")
        
    def handleBootloaderMode(self, udevinfo):
        """Device action handler for BOOTLOADER mode. Looks for partition devs and uploads
        the firmware to them."""

        if udevinfo.get("SUBSYSTEM") == "tty":
            send_bootloader(udevinfo["DEVNAME"])
            self.logger.info(f"sending bootloader signal to {udevinfo["DEVNAME"]}")

        elif udevinfo.get("DEVTYPE") == "partition":
            self.logger.info(f"found bootloader candidate {udevinfo["DEVNAME"]} for {self.serial}")
            path = os.path.join("media", self.serial)
            if not os.path.isdir(path):
                os.mkdir(path)
            
            firmware_bytes = files("worker").joinpath("firmware").joinpath("build").joinpath("default_firmware.uf2").read_bytes()

            try:
                uploaded = upload_firmware(udevinfo["DEVNAME"], path, firmware_bytes)
                if uploaded:
                    self.endBootloaderMode()
                    self.trackDevice(udevinfo)
                else:
                    self.logger.warning(f"detected potential bootloader drive for {self.serial} device {format_dev_file(udevinfo)} but failed to upload firmware")

            except FirmwareUploadFail:
                self.logger.error(f"firmware upload left in unknown state for device {self.serial} after uploading to {format_dev_file(udevinfo)}")
                self.database.updateDeviceStatus(self.serial, "broken")
                self.mode = Mode.BROKEN
    
    def handleBootloaderTimeout(self):
        with self.lock:
            if self.mode != Mode.BOOTLOADER:
                return

            self.mode = Mode.BROKEN
            self.database.updateDeviceStatus(self.serial, "broken")
            self.database.sendDeviceSubscription(self.serial, {
                "event": "disconnect",
                "serial": self.serial
            })
            self.logger.error(f"device {self.serial} timed out while flashing default firmware")

    def handleTestAdd(self, udevinfo):
        """Device action handler for TEST mode. Checks whether a device is 
        printing the default firmware message."""
        path = udevinfo.get("DEVNAME")

        if not path:
            self.logger.warning(f"expected default firmware dev on device {self.serial} but was no devname")
        
        if not check_default(path):
            self.logger.warning(f"default firmware test for {self.serial} failed")
            self.database.updateDeviceStatus(self.serial, "broken")
            self.mode = Mode.BROKEN
            return 

        self.logger.info(f"{self.serial} now available")
        
        self.mode = Mode.NORMAL

        self.database.updateDeviceStatus(self.serial, "available")
        self.handleAddDevice(udevinfo, have_lock=True)

    def endBootloaderMode(self):
        """Cleanup after firmware is uploaded"""
        if self.mode != Mode.BOOTLOADER:
            return

        self.logger.info(f"restored default firmware to {self.serial}")
        self.bootloader_timeout_clock.cancel()
        self.bootloader_timeout_clock = None
        self.mode = Mode.TEST
        self.database.updateDeviceStatus(self.serial, "testing")

    def handleUsbipDisconnect(self):
        """Event handler for when a usbip disconnect is detected"""
        with self.lock:
            self.logger.info(f"device {self.serial} on bus {self.exported_busid} disconnected while exporting usbip")
            self.exported_busid = None
            self.database.removeDeviceBus(self.serial)
            self.database.sendDeviceSubscription(self.serial, {
                "event": "disconnect",
                "serial": self.serial
            })