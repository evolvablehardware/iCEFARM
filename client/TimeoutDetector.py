import time
import threading
import pyudev

from client.EventHandler import EventHandler
from utils.dev import get_serial
from utils.usbip import usbip_port
from utils.utils import *


class DeviceStatus:
    def __init__(self, serial, ip, bus, timeout=20, delay=15):
        self.serial = serial
        self.ip = ip
        self.bus = bus
        self.last_event = time.time()
        self.timeout = timeout
        self.delay = delay
        self.lock = threading.Lock()

        self.timed_out = False
    
    def updateBus(self, bus):
        with self.lock:
            self.bus = bus
            self.last_event = max(time.time(), self.last_event)
    
    def deviceEvent(self):
        with self.lock:
            self.last_event = max(time.time(), self.last_event)
    
    def checkTimeout(self, info):
        with self.lock:
            if self.ip in info:
                if self.bus in info[self.ip]:
                    self.last_event = time.time()

            self.timed_out = time.time() - self.timeout > self.last_event
    
    def hadTimeout(self):
        with self.lock:
            if self.timed_out:
                self.last_event = time.time() + self.delay
            return self.timed_out

class TimeoutDetector(EventHandler):
    def __init__(self, client, logger, poll=4, timeout=15):
        self.client = client
        self.logger = logger

        self.devices = {}
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
        while True:
            for _ in range(self.poll):
                if self.stop_poll_thread:
                    break
                time.sleep(1)
            
            info= usbip_port()

            if info == False:
                self.logger.warning("usbip port failed")
                return
            
            for dev in self.devices:
                if self.devices[dev].checkTimeout(info):
                    self.logger.warning(f"device {dev} timed out")
            
            for dev in self.devices.keys():
                if self.devices[dev].hadTimeout():
                    self.devices[dev].deviceEvent()
                    self.client.triggerTimeout(dev)

    def handleExport(self, client, serial, bus, worker_ip, worker_port):
        with self.lock:
            if serial not in self.devices:
                self.devices[serial] = DeviceStatus(serial, worker_ip, bus, timeout=self.timeout)
                return
        
            self.devices[serial].updateBus(bus)
    
    def __removeDevice(self, serial):
        with self.lock:
            if serial not in self.devices:
                return False
            
            del self.devices[serial]
            return True

    def handleReservationEnd(self, client, serial):
        self.__removeDevice(serial)

    def handleFailure(self, client, serial):
        self.__removeDevice(serial)
    
    def exit(self, client):
        self.observer.send_stop()
        self.stop_poll_thread = True
        self.poll_thread.join()
    
    def handleDisconnect(self, client, serial):
        pass
    
    def handleReservationEndingSoon(self, client, serial):
        pass
    
    def handleTimeout(self, client, serial, ip, port):
        pass


    
    