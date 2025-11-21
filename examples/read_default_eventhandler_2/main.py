import logging
import sys
import os
import time

import atexit
from pexpect import fdpexpect

from client.Client import Client
from client.EventHandler import DefaultEventHandler, EventHandler
from client.TimeoutDetector import TimeoutDetector

from utils.dev import get_dev_paths
from utils.utils import get_ip

#################################################
CLIENT_NAME = "read default example"
CLIENT_IP = get_ip() # local network ip - must be accessible by control/worker servers
CLIENT_PORT = "8080"
CONTROL_SERVER = ""

if not CONTROL_SERVER:
    CONTROL_SERVER = os.environ.get("USBIPICE_CONTROL_SERVER")
#################################################

if not (CLIENT_NAME and CLIENT_IP and CLIENT_PORT and CONTROL_SERVER):
    raise Exception("Configuration error.")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

client = Client(CLIENT_NAME, CONTROL_SERVER, logger)
event_handlers = []
event_handlers.append(DefaultEventHandler(logger))
event_handlers.append(TimeoutDetector(client, logger))

# We can define our own EventHandlers to add to the EventServer
class ReadOnExport(EventHandler):
    def handleExport(self, client: Client, serial: str, bus, worker_ip, worker_port):
        # This is the event thats called when a reserved device starts to
        # export over usbip ip. The bus, worker_ip, and worker_port arguments
        # are used to establish a connection, but are not needed here -
        # the DefaultEventHandler takes care of connecting with usbip for us.

        # Same reading process as the read_default_firmware_1 example.
        # Still need to sleep because it takes time for device files to show
        # up after a connection.

        # Note: This behavior would be better implemented using
        # pyudev events, but this is a natural extension of the first
        # example.

        time.sleep(2)
        device_paths = get_dev_paths()

        if serial not in device_paths:
            raise Exception("Unable to find device file.")

        dev_path = device_paths[serial][0]

        tty = os.open(dev_path, os.O_RDWR)
        p = fdpexpect.fdspawn(tty, timeout=5)
        p.expect("default firmware")
        print(f"Got response from device {serial}!")
        p.close()


event_handlers.append(ReadOnExport())

client.startEventServer(event_handlers, CLIENT_IP, CLIENT_PORT)

serials = client.reserve(2)
atexit.register(lambda : client.end(serials))

if len(serials) != 2:
    raise Exception("Failed to reserve two devices.")

# Wait for devices to be read from
time.sleep(15)

client.stopEventServer()
