import pyudev
import threading
import os

from utils.dev import *
from utils.utils import *

class Device:
    def __init__(self, serial, firmware_path, flasher):
        self.serial = serial
        self.firmware_path = firmware_path
        self.flasher = flasher

        self.lock= threading.Lock()
        self.upload_finished = False

    def ttyExport(self, path):
        with self.lock:
            if self.upload_finished:
                self.markDone()
                return

            send_bootloader(path)

    def partExport(self, path):
        mount_path = os.path.join("client_media", self.serial)
        if not os.path.exists(mount_path):
            os.mkdir(mount_path)

        with self.lock:
            try:
                upload_firmware_path(path, mount_path, self.firmware_path, mount_timeout=30)
            except FirmwareUploadFail:
                self.markFailed()
            else:
                self.upload_finished = True

    def otherExport(self, path):
        with self.lock:
            if self.upload_finished:
                self.markDone()

    def markDone(self):
        self.flasher.handleDone(self.serial)

    def markFailed(self):
        self.flasher.handleFailed(self.serial)

class FirmwareFlasher:
    """Used to flash firmware."""
    def __init__(self):
        self.remaining_serials = {}
        self.failed_serials = []

        self.timeout = None
        self.timeout_thread = None

        self.cv = threading.Condition()

        if not os.path.exists("client_media"):
            os.mkdir("client_media")

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        self.observer = pyudev.MonitorObserver(monitor, lambda x, y: self.__handle_event(x, y), name="flash-observer")

    def startFlasher(self):
        """Start monitoring for device events."""
        if not self.observer.is_alive():
            self.observer.start()

    def __handle_event(self, action, dev):
        """Reroutes events to corresponding Device objects."""
        if action != "add":
            return

        dev = dict(dev)

        serial = get_serial(dev)

        if not serial:
            return

        path = dev.get("DEVNAME")

        if not path:
            return

        with self.cv:
            if serial not in self.remaining_serials:
                return

            device = self.remaining_serials[serial]

        if dev.get("SUBSYSTEM") == "tty":
            device.ttyExport(path)
        elif dev.get("DEVTYPE") == "partition":
            device.partExport(path)
        else:
            device.otherExport(path)

    def flash(self, serials: list[str], path: str):
        """Queue serials to be flashed with path firmware. Note that this does not return when the devices 
        are done being flashed, only once the devices have been added into the queue."""
        if not isinstance(serials, list):
            serials = [serials]

        with self.cv:
            for serial in serials:
                self.remaining_serials[serial] = Device(serial, path, self)

        info = get_devs()
        devs = []

        for serial, path in info.items():
            if serial in serials:
                devs.extend(path)


        for file in devs:
            if file.get("SUBSYSTEM") != "tty":
                return

            if (path := file.get("DEVNAME")):
                send_bootloader(path)

    def handleDone(self, serial):
        with self.cv:
            self.remaining_serials.pop(serial)

            if not self.remaining_serials:
                self.cv.notify_all()

    def handleFailed(self, serial):
        with self.cv:
            if not self.remaining_serials.pop(serial):
                return

            self.failed_serials.append(serial)

            if not self.remaining_serials:
                self.cv.notify_all()

    def waitUntilFlashingFinished(self, timeout=None) -> tuple[list, list]:
        """Returns when all of the devices in the queue are done being flashed to, after timeout seconds, or if the flasher is stopped.
        Returns the serials that failed to flash in the given time.
        """
        timer = None

        def ontimeout():
            with self.cv:
                self.failed_serials.extend(self.remaining_serials.keys())
                self.remaining_serials = {}
                self.cv.notify_all()

        if timeout:
            timer = threading.Timer(timeout, ontimeout)
            timer.start()

        with self.cv:
            self.cv.wait_for(lambda : not self.remaining_serials)

        if timer:
            timer.cancel()

        with self.cv:
            failed = self.failed_serials
            self.failed_serials = []
            return failed

    def stopFlasher(self):
        """Stops monitoring for device events. Marks all devices currently flashing as failed to flash."""
        if self.observer.is_alive():
            self.observer.send_stop()

        with self.cv:
            self.failed_serials.extend(self.remaining_serials.keys())
            self.remaining_serials = {}
            self.cv.notify_all()
