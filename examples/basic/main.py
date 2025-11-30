import logging
import sys
import os
import time

import atexit
from pexpect import fdpexpect

from usbipice.client.drivers.usbip import UsbipClient
from usbipice.utils import get_ip
from usbipice.utils.dev import get_dev_paths

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
client.start(CLIENT_IP, CLIENT_PORT)

# Device serials serve as a device's unique ID
serials = client.reserve(1)

# End the reservation on exit. If we don't,
# the devices will be inaccessible for the remainder
# of the reservation (~1h).
# client.stop() also does this, but it won't
# happen if an exception occurs beforehand.
atexit.register(lambda : client.endAll)

if not serials:
    raise Exception("Failed to reserve a device.")

# Serial of the reserved device
serial = serials[0]
logger.info(f"Reserved device {serial}!")


# Give some time for usbip connections to happen.
# This should be detected using EventHandlers or pyudev,
# but as a first example this is much simpler.
time.sleep(5)

# Returns a dict mapping pico2ice device serials to lists
# of their device files. This contains information
# about all of the devices connected to the system,
# not just those from this client.
device_paths = get_dev_paths()

if serial not in device_paths:
    # If there's a lot of network latency this could happen.
    raise Exception("Unable to find device file.")

dev_path = device_paths[serial][0]

# Read from device
tty = os.open(dev_path, os.O_RDWR)
p = fdpexpect.fdspawn(tty, timeout=5)
p.expect("default firmware")
print("Read from device!")
p.close()

# Stops EventServer threads and sends exit signal
# to EventHandlers so they can cleanup
# An exit won't happen unless until this is called
client.stop()
