import logging
import pyudev
import re
import sys
import subprocess
from threading import Lock

from utils import *
    
class Device:
    def __init__(self, serial, logger, dev_files={}):
        self.serial = serial
        self.logger = logger
        self.dev_files = dev_files
        self.exported_devices = {}

        self.available = True
        self.lock = Lock()

    def handleAddDevice(self, udevinfo):
        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} addDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier in self.dev_files.keys():
            self.logger.error(f"device {format_dev_file({udevinfo})} added but already exists, overwriting")
        
        self.dev_files[identifier] = udevinfo
        
        self.logger.info(f"added dev file {format_dev_file(udevinfo)}")

        if True:
            busid = get_busid(udevinfo)
            #TODO verify this works
            subprocess.run(["sudo", "usbip", "bind", "-b", busid])
        
            if busid not in self.exported_devices.keys():
                self.exported_devices[busid] = {}
            
            self.exported_devices[busid] = udevinfo
    
    def handleRemoveDevice(self, udevinfo):
        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier not in self.dev_files.keys():
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: dev file under major/minor does not exist, ignoring")
            return
        
        del self.dev_files[identifier]

        busid = get_busid(udevinfo)

        if busid not in self.exported_devices.keys():
            return
        
        if identifier not in self.exported_devices[busid]:
            return
        
        del self.exported_devices[busid][identifier]

        self.logger.info(f"removed device {format_dev_file(udevinfo)}")
    
    def reserve(self):
        with self.lock:
            if not self.available:
                return False
            
            self.available = False
            return True
    
    def unreserve(self):
        with self.lock:
            if self.available:
                return False
            
            self.available = True
            return True

class DeviceManager:
    def __init__(self, logger):
        self.logger = logger
        self.devs = {}

        def handle_dev_events(dev):
            attributes = dict(dev.properties)

            devname = attributes.get("DEVNAME")


            if not devname:
                return

            if not re.match("/dev/", devname) or re.match("/dev/bus/", devname):
                return

            id_model = attributes.get("ID_MODEL")

            if id_model != "RP2350" and id_model != 'pico-ice':
                return 
            
            serial = attributes.get("ID_SERIAL_SHORT")

            if not serial:
                return

            if dev.action == "add":
                self.handleAddDevice(serial, attributes)
            elif dev.action == "remove":
                self.handleRemoveDevice(serial, attributes)
            else:
                logger.warning(f"Unhandled action type {dev.action} for {format_dev_file(attributes)}")

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, callback=handle_dev_events, name='monitor-observer')
        observer.start()


    def handleAddDevice(self, serial, udevinfo):
        if serial not in self.devs:
            self.logger.info(f"Creating device with serial {serial}")
            self.devs[serial] = Device(serial, self.logger)
        
        self.devs[serial].handleAddDevice(udevinfo)

    def handleRemoveDevice(self, serial, udevinfo):
        if serial not in self.devs:
            self.logger.warning(f"tried to remove dev file {format_dev_file(udevinfo)} but does not exist")
            return
        
        self.devs[serial].handleRemoveDevice(udevinfo)
    
    def getDevices(self):
        values = []

        for d in self.devs:
            values.append(d.serial)
        
        return values
    
    def getDevicesAvailable(self):
        values = []

        for d in self.devs.values():
            if d.available:
                values.append(d.serial)
        
        return values

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    manager = DeviceManager(logger)

    import time
    time.sleep(500)