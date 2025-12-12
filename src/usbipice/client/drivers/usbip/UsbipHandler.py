import time
import threading
from logging import Logger

import pyudev

from usbipice.client.lib.usbip import UsbipBaseClient, BaseUsbipEventHandler, register
from usbipice.client.lib import EventServer

from usbipice.utils.dev import get_serial
from usbipice.utils.usbip import usbip_port, usbip_attach

class DeviceStatus:
    """"Tracks what bus a device is on and the last time it had activity."""
    def __init__(self, serial: str, ip: str, bus: str, timeout: int=20, delay: int=15):
        self.serial = serial
        self.ip = ip
        self.bus = bus
        self.last_event = time.time()
        self.timeout = timeout
        self.delay = delay
        self.lock = threading.Lock()

        self.timed_out = False

    def updateBus(self, bus: str):
        """Updates bus device is accessible on, updates last_event."""
        with self.lock:
            self.bus = bus
            self.last_event = max(time.time(), self.last_event)

    def deviceEvent(self):
        """Updates last_event."""
        with self.lock:
            self.last_event = max(time.time(), self.last_event)

    def checkTimeout(self, info):
        """Set timed_out to whether the device as timed out. Takes {ip -> [buses]}."""
        with self.lock:
            if self.ip in info:
                if self.bus in info[self.ip]:
                    self.last_event = time.time()

            self.timed_out = time.time() - self.timeout > self.last_event

    def hadTimeout(self) -> bool:
        """Returns whether the device had a timeout. If it did, prevent further timeouts until the timeout delay is reached."""
        with self.lock:
            if self.timed_out:
                self.last_event = time.time() + self.delay
            return self.timed_out

class UsbipHandler(BaseUsbipEventHandler):
    """EventHandler for detecting usbip timeouts through tracking device events and polling usbip port. When
    a timeout is detected, it calls triggerTimeout on the client to inform other EventHandlers."""
    def __init__(self, event_server: EventServer, api: UsbipBaseClient, logger: Logger, poll=4, timeout=15):
        super().__init__(event_server)

        self.api = api
        self.logger = logger

        self.devices: dict[str, DeviceStatus] = {}
        self.lock = threading.Lock()

        self.poll = poll
        self.timeout = timeout

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        self.observer = pyudev.MonitorObserver(monitor, lambda x, y : self.__handleDevEvent(x, y), name="timeoutdetector-observer")

        self.stop_poll_thread = False
        self.poll_thread = threading.Thread(target=lambda : self.__pollUsbipPort(), name="timeoutdetector-poll")
        self.poll_thread.start()

    def __handleDevEvent(self, event, dev):
        if event != "add":
            return

        serial = get_serial(dict(dev))

        if not serial:
            return

        with self.lock:
            if serial not in self.devices:
                return

            self.devices[serial].deviceEvent()

    def __pollUsbipPort(self):
        """Runs usbip port, updates devices that are connected, and triggers timeouts on devices that 
        have disconnected."""
        while True:
            for _ in range(self.poll):
                if self.stop_poll_thread:
                    return
                time.sleep(1)

            info = usbip_port()

            if info is False:
                self.logger.warning("usbip port failed")
                return

            for serial, dev in self.devices.items():
                if dev.checkTimeout(info):
                    self.logger.warning(f"device {serial} timed out")

            for serial, dev in self.devices.items():
                if dev.hadTimeout():
                    self.logger.warning(f"device {serial} timed out")
                    dev.deviceEvent()
                    self.api.unbind(serial)

    def export(self, serial: str, busid: str, server_ip: str, usbip_port: str):
        if usbip_attach(server_ip, busid, tcp_port=usbip_port):
            self.logger.info(f"bound device {serial} on {server_ip}:{usbip_port}:{busid}")
        else:
            self.logger.error(f"failed to bind device {serial} on {server_ip}:{usbip_port}:{busid}")

        with self.lock:
            if serial not in self.devices:
                self.devices[serial] = DeviceStatus(serial, server_ip, busid, timeout=self.timeout)
                return

            self.devices[serial].updateBus(busid)

    def __removeDevice(self, serial: str):
        with self.lock:
            if serial not in self.devices:
                return False

            del self.devices[serial]
            return True

    @register("reservation end", "serial")
    def handleReservationEnd(self, serial: str):
        self.__removeDevice(serial)

    @register("failure", "serial")
    def handleFailure(self, serial: str):
        self.__removeDevice(serial)

    def exit(self):
        self.observer.send_stop()
        self.stop_poll_thread = True
        self.poll_thread.join()
