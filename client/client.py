from flask import Flask, request, Response
import threading
from abc import ABC, abstractmethod
import subprocess
import requests
import pyudev
import threading
import time

from utils.utils import *

def service(port, eventhandler, client):
    app = Flask(__name__)

    @app.route("/")
    def handle():
        if request.content_type != "application/json":
            return Response(400)
        
        try:
            json = request.get_json()
        except:
            return Response(400)
        
        event = json.get("event")

        if not event:
            return Response(400)
        
        serial = json.get("serial")

        if not serial:
            return Response(400)

        match event:
            case "failure":
                eventhandler.handleFailure(serial)
            case "reservation end":
                eventhandler.handleReservationEnd(serial)
                pass
            case "export":
                connection_info = client.getConnectionInfo(serial)

                if not connection_info:
                    return Response(400)
                
                ip, port = connection_info

                bus = json.get("bus")

                if not bus:
                    return Response(400)

                eventhandler.handleExport(serial, bus, ip, port)
            case "disconnect":
                eventhandler.handleDisconnect(serial)
            case "reservation halfway":
                eventhandler.handleReservationHalfway(serial)
            case _:
                return Response(400)

    app.run(port=port)

class EventHandler(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def handleExport(self, serial, bus, worker_ip, worker_port):
        """This is called when the host worker exports a reserved device."""
        pass

    @abstractmethod
    def handleDisconnect(self, serial):
        """This is called when the host worker is no longer exporting the device with usbip.
        This can happen normally, for example, during reboot after a firmware change. However, 
        if it's unexpected something probably went wrong."""
        pass

    @abstractmethod
    def handleReservationEnd(self, serial):
        """This is called when a devices reservation ends. The device will be unbound from the workers side -
        there is no way to retain access to a device after the reservation is over."""
        pass

    @abstractmethod
    def handleReservationEndingSoon(self, serial):
        """This is called when a reservation is halfway over. It is intended to be used to extend
        the reservation time."""
        pass

    @abstractmethod
    def handleFailure(self, serial):
        """This is called when a device failure occurs that is unrecoverable, such as the host worker failing
        a heartbeat check. It is not possible to connect back to the device."""
        pass

class DefaultEventHandler(EventHandler):
    def __init__(self, client_name, control_server_url, logger):
        super().__init__()
        self.client_name = client_name
        self.control_server_url = control_server_url
        self.logger = logger
    
    def handleExport(self, serial, bus, worker_ip, worker_port):
        try:
            p = subprocess.run(["sudo", "usbip", "--tcp-port", worker_port, "attach", "-r", worker_ip, "-b", bus], timeout=5)
            if p.returncode != 0:
                raise Exception

        except:
            self.logger.error(f"failed to bind device {serial} on {worker_ip}:{bus}")
        else:
            self.logger.info(f"bound device {serial} on {worker_ip}:{bus}")
    
    def handleDisconnect(self, serial):
        self.logger.warning(f"device {serial} disconnected")
    
    def handleReservationEndingSoon(self, serial):
        try:
            res = requests.get(f"{self.control_server_url}/extend", data={
                "name": self.client_name,
                "serials": [serial]
            })

            if res.status_code != 200:
                raise Exception
        
        except:
            self.logger.error(f"failed to refresh reservation of {serial}")
        else:
            self.logger.info(f"refreshed reservation of {serial}")
    
    def handleReservationEnd(self, serial):
        self.logger.info(f"reservation for device {serial} ended")
    
    def handleFailure(self, serial):
        self.logger.error(f"device {serial} failed")
    

class Client:
    def __init__(self, clientname, control_server_url):
        # serial -> (ip, port)
        self.serial_locations = {}
        self.clientname = clientname
        self.control_server_url = control_server_url

        self.thread = None
    
    def getConnectionInfo(self, serial):
        """Returns the (ip, port) needed to connect to a device with usbip."""
        return self.serial_locations.get(serial)

    def startService(self, port, eventhandler):
        """Starts listening for device events on the specified port using the eventhandler."""
        self.thread = threading.Thread(target=lambda : service(port, eventhandler, self))
        self.thread.start()

    def reserve(self, amount):
        """Reserves and connects to the specified amount of devices and returns their serials.
        If there are not enough devices available, it will reserve as many as it can."""
        try:
            data = requests.get(f"{self.control_server_url}/reserve", data={
                "amount":amount,
                "name": self.name
            })

            json = data.json()
        except:
            return False
        
        connections = []

        for row in json:
            try:
                serial = row["serial"]
                ip = row["ip"]
                port = row["usbipport"]
                bus = row["bus"]

                p = subprocess.run(["sudo", "usbip", "--tcp-port", port, "attach", "-r", ip, "-b", bus], timeout=5)

                if p.returncode != 0:
                    raise Exception
                
                connections.append(serial)
                self.serial_locations[serial] = (ip, port)
            except:
                #TODO disconnect
                pass
        
        return connections

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
            
            out[serial].append(devname)
        
        return out

    def flash(self, serials, firmware_path, timeout=1):
        """Flashes firmware_path to serials. Requires that the listed devices respond to the 1200 baud
        protocol. Returns a list of serials that failed to flash. Returns after all devices have been updated, or
        after timeout seconds. Devices that fail to be flashed to should be considered in an unknown state and unreserved."""
        if type(serials) != list:
            serials = [serials]

        if not os.path.exists("client_media"):
            os.mkdir("client_media")

        dev_files = self.getDevs(serials)

        # release when ready to return
        return_lock = threading.Lock()
        return_lock.acquire()

        # stops data modification after return while observer shuts down
        data_lock = threading.Lock()

        remaining_serials = set(serials) 
        failed_serials = []

        def handle_event(action, dev):
            if action != "add":
                return
            
            dev = dict(dev)

            if dev.get("DEVTYPE") != "partition":
                return
            
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
                if upload_firmware(devname, mount_path, b):
                    with data_lock:
                        remaining_serials.remove(serial)

            except FirmwareUploadFail:
                with data_lock:
                    remaining_serials.remove(serial)
                    failed_serials.append(serial)
            
            with data_lock:
                if not remaining_serials:
                    observer.send_stop()
                    return_lock.release()

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, handle_event, name="client-pyudev-monitor")
        observer.start()

        exit_timeout = False

        if timeout:
            def handle_timeout():
                for _ in range(timeout):
                    time.sleep(1)

                    if exit_timeout:
                        return

                observer.send_stop()
                return_lock.release()
            
            threading.Thread(target=handle_timeout).start()

        for device in dev_files.values():
            for file in device:
                if (path := file.get("DEVNAME")):
                    send_bootloader(path)
        
        return_lock.acquire()
        exit_timeout = True
        data_lock.acquire()

        for serial in remaining_serials:
            failed_serials.append(serial)

        return failed_serials

    def extend(self, serials):
        try:
            res = request.get(f"{self.control_server_url}/extend", data={
                "name": self.clientname,
                "serials": serials
            })

            if res.status_code != 200:
                raise Exception
            
            return res.json()
        except:
            return False


    def extendAll(self):
        try:
            res = request.get(f"{self.control_server_url}/extendall", data={
                "name": self.clientname,
            })

            if res.status_code != 200:
                raise Exception
            
            return res.json()
        except:
            return False

    def end(self, serials):
        try:
            res = request.get(f"{self.control_server_url}/end", data={
                "name": self.clientname,
                "serials": serials
            })

            if res.status_code != 200:
                raise Exception
            
            return res.json()
        except:
            return False

    def endAll(self):
        try:
            res = request.get(f"{self.control_server_url}/endall", data={
                "name": self.clientname,
            })

            if res.status_code != 200:
                raise Exception
            
            return res.json()
        except:
            return False