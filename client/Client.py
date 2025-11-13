from flask import Flask, request, Response
import threading
import requests
import pyudev
import threading
import time
from waitress.server import create_server

from utils.utils import *

class Client:
    def __init__(self, clientname, control_server_url):
        # serial -> (ip, port)
        self.serial_locations = {}
        self.clientname = clientname
        self.control_server_url = control_server_url

        self.service_url = None
        self.eventhandler = None

        self.thread = None
        self.server = None
    
    def getConnectionInfo(self, serial):
        """Returns the (ip, port) needed to connect to a device with usbip."""
        return self.serial_locations.get(serial)

    def startService(self, port, eventhandler):
        """Starts listening for device events on the specified port using the eventhandler."""
        self.service_url = f"http://{getIp()}:{port}"
        self.eventhandler = eventhandler
        app = Flask(__name__)

        @app.route("/")
        def handle():
            if request.content_type != "application/json":
                return Response(400)
            
            try:
                json = request.get_json()
            except:
                return Response(400)
            
            serial = json.get("serial")
            event = json.get("event")

            if not serial or not event:
                return Response(400)

            match event:
                case "failure":
                    eventhandler.handleFailure(serial)
                case "reservation end":
                    eventhandler.handleReservationEnd(serial)
                    pass
                case "export":
                    connection_info = self.getConnectionInfo(serial)

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
        
        self.server = create_server(app, port=port)
        self.thread = threading.Thread(target=lambda : self.server.run())
        self.thread.start()
    
    def stopService(self):
        self.server.close()
        self.thread.join()

    def reserve(self, amount):
        """Reserves and connects to the specified amount of devices and returns their serials.
        If there are not enough devices available, it will reserve as many as it can."""
        if not self.service_url or not self.eventhandler:
            raise Exception("no service started")

        try:
            data = requests.get(f"{self.control_server_url}/reserve", json={
                "amount":amount,
                "name": self.clientname,
                "url": self.service_url
            })

            json = data.json()
        except Exception:
            return False
        
        connections = []

        for row in json:
            self.serial_locations[row["serial"]] = (row["ip"], row["usbipport"])
            self.eventhandler.handleExport(row["serial"], row["bus"], row["ip"], row["usbipport"])
            connections.append(row["serial"])
        
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
            res = requests.get(f"{self.control_server_url}/extend", json={
                "name": self.clientname,
                "serials": serials
            })

            if res.status_code != 200:
                raise Exception
            
            return res.json()
        except Exception:
            return False


    def extendAll(self):
        try:
            res = requests.get(f"{self.control_server_url}/extendall", json={
                "name": self.clientname,
            })

            if res.status_code != 200:
                raise Exception
            
            return res.json()
        except Exception:
            return False

    def end(self, serials):
        try:
            res = requests.get(f"{self.control_server_url}/end", json={
                "name": self.clientname,
                "serials": serials
            })

            if res.status_code != 200:
                raise Exception
            
            return res.json()
        except Exception as e:
            return False

    def endAll(self):
        try:
            res = requests.get(f"{self.control_server_url}/endall", json={
                "name": self.clientname,
            })

            if res.status_code != 200:
                raise Exception
            
            return res.json()
        except Exception:
            return False