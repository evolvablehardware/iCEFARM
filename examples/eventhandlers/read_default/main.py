import logging
import sys
import os
import time

import atexit
from pexpect import fdpexpect

from usbipice.client.drivers.usbip import UsbipClient

# client.base provides tools for working with a specific type of device reservation
# The EventHandler abstract class provides a way for us to respond to events
# from the worker.
from usbipice.client.lib.usbip import BaseUsbipEventHandler

# Used for typing, ignore
from usbipice.client.lib import EventServer

from usbipice.utils.dev import get_dev_paths
from usbipice.utils import get_ip

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

client = UsbipClient(CONTROL_SERVER, CLIENT_NAME, logger)
atexit.register(lambda : client.endAll)

class ReadOnExport(BaseUsbipEventHandler):
    # The EventServer can be obtained from UsbipClient.getEventServer()
    def __init__(self, event_server: EventServer, logger: logging.Logger):
        super().__init__(event_server)
        self.logger = logger

    def export(self, serial:str, busid: str, server_ip: str, usbip_port: str):
        # This is the method thats called when a reserved device starts to
        # export over usbip ip. The bus, worker_ip, and worker_port arguments
        # are used to establish a connection, but are not needed here - other
        # eventhandlers included with UsbipClient will take care of that for us.

        # In BaseUsbipEventHandler, this method is marked with a decorator.
        # This does not need to be done in classes that inherit from it.

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
        logger.info(f"Read from device {serial}!")
        p.close()

read_on_export = ReadOnExport(client.getEventServer(), logger)
# Eventhandlers are added when starting the client. Internally,
# this starts the EventServer.
client.start(CLIENT_IP, CLIENT_PORT, event_handlers=[read_on_export])

# Reserve two devices to demonstrate that ReadOnExport
# responds to both independently
serials = client.reserve(2)

if not serials or len(serials) != 2:
    raise Exception("Failed to reserve two devices.")

logger.info(f"Reserved two devices: {serials}")

# Wait for devices to be read from
time.sleep(15)
client.stop()
