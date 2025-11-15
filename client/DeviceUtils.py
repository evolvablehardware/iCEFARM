import pyudev
import threading
import os
import time

from utils.dev import *
from utils.utils import *

# TODO refactor
class DeviceUtils:
    def getDevs(self, serials):
        """Returns a dict mapping device serials to list of dev info dicts. This operation 
        looks through all available dev files and is intended to be only used once after reserving devices.
        If you are dealing with frequent dev file changes, you should use a pyudev MonitorObserver instead."""
        out = {}

        context = pyudev.Context().list_devices()
        for dev in context:
            values = dict(dev)
            serial = get_serial(values)

            if not serial:
                continue
            
            if serial not in serials:
                continue

            devname = values.get("DEVNAME")

            if not devname:
                continue

            if serial not in out:
                out[serial] = []
            
            out[serial].append(dev)
        
        return out

    def getDevPaths(self, serials):
        """Returns a dict mapping device serials to list of dev paths. This operation 
        looks through all available dev files and is intended to be only used once after reserving devices.
        If you are dealing with frequent dev file changes, you should use a pyudev MonitorObserver instead."""
        out = self.getDevs(serials)
        for key in out:
            items = map(lambda x : x.get("DEVNAME"), out[key])
            filtered = filter(lambda x : x, items)
            out[key] = list(filtered)
        
        return out

    def flash(self, serials, firmware_path, timeout=1):
        """Flashes firmware_path to serials. Requires that the listed devices respond to the 1200 baud
        protocol. Returns a list of serials that failed to flash. Returns after all devices have been updated, or
        after timeout seconds. Devices that fail to be flashed to should be considered in an unknown state and unreserved."""
        if type(serials) != list:
            serials = [serials]

        if not os.path.exists("client_media"):
            os.mkdir("client_media")

        # release when ready to return
        return_lock = threading.Lock()
        return_lock.acquire()

        # stops data modification after return while observer shuts down
        data_lock = threading.Lock()

        dev_files = []

        remaining_serials = set(serials) 
        failed_serials = []

        def handle_event(action, dev):
            if action != "add":
                return
            
            dev = dict(dev)

            if dev.get("SUBSYSTEM") == "tty":
                serial = get_serial(dev)

                if not serial or serial not in remaining_serials:
                    return
                
                devname = dev.get("DEVNAME")

                if not devname:
                    return
                
                send_bootloader(devname)

            elif dev.get("DEVTYPE") == "partition":
                serial = get_serial(dev)

                if not serial or serial not in remaining_serials:
                    return
                
                devname = dev.get("DEVNAME")

                if not devname:
                    return
                
                with open(firmware_path, "rb") as f:
                    b = f.read()
                
                mount_path = os.path.join("client_media", serial)
                if not os.path.exists(mount_path):
                    os.mkdir(mount_path)

                try:
                    if upload_firmware(devname, mount_path, b, mount_timeout=30):
                        with data_lock:
                            remaining_serials.remove(serial)

                except FirmwareUploadFail:
                    with data_lock:
                        remaining_serials.remove(serial)
                        failed_serials.append(serial)
            
                with data_lock:
                    done = len(remaining_serials) == 0
                
                if done:
                    return_lock.release()
                    observer.send_stop()

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, handle_event, name="flash-observer")
        observer.start()

        dev_files = self.getDevs(serials)

        exit_timeout = False

        if timeout:
            def handle_timeout():
                for _ in range(timeout):
                    time.sleep(1)

                    if exit_timeout:
                        return

                observer.send_stop()
                return_lock.release()
            
            threading.Thread(target=handle_timeout, name="flash-timeout-detection").start()

        for device in dev_files.values():
            for file in device:
                if file.get("SUBSYSTEM") != "tty":
                    return

                if (path := file.get("DEVNAME")):
                    send_bootloader(path)
        
        return_lock.acquire()
        exit_timeout = True
        data_lock.acquire()

        for serial in remaining_serials:
            failed_serials.append(serial)

        return failed_serials