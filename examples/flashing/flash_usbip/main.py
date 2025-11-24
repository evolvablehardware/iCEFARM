import logging
import sys
import os
import signal

from client.Client import Client
from client.EventHandler import DefaultEventHandler
from client.TimeoutDetector import TimeoutDetector
from client.FirmwareFlasher import FirmwareFlasher

from utils.utils import get_ip

#################################################
CLIENT_NAME = "read default example"
CLIENT_IP = get_ip() # local network ip - must be accessible by control/worker servers
CLIENT_PORT = "8080"
CONTROL_SERVER = ""
FIRMWARE_PATH = ""

if not CONTROL_SERVER:
    CONTROL_SERVER = os.environ.get("USBIPICE_CONTROL_SERVER")
#################################################

if not (CLIENT_NAME and CLIENT_IP and CLIENT_PORT and CONTROL_SERVER and FIRMWARE_PATH):
    raise Exception("Configuration error.")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

client = Client(CLIENT_NAME, CONTROL_SERVER, logger)

event_handlers = [DefaultEventHandler(logger), TimeoutDetector(client, logger)]
client.startEventServer(event_handlers, CLIENT_IP, CLIENT_PORT)

serials = client.reserve(1)

# Firmware flasher
flasher = FirmwareFlasher()

def handler(sig, frame):
    print("Exiting...")
    client.endAll()
    # The flasher creates separate threads
    # that need to be stopped for a graceful
    # exit
    flasher.stopFlasher()
    sys.exit()

signal.signal(signal.SIGINT, handler)


if not serials:
    raise Exception("Failed to reserve a device.")
serial = serials[0]

# Start monitoring for device events.
flasher.startFlasher()
# Add the reserved device to the flash queue -
# this does NOT exit when the flashing is done.
flasher.flash(serial, FIRMWARE_PATH)
# This will return there are no serials left to flash to,
# the timeout is reached, or stopFlasher is called.
# The remaining serials are still in the flasher queue; they
# are still being flashed to, but the process has not completed yet.
# This could be an indication that the firmware does not follow the baud
# 1200 protocol however. A device is put into failed_serials when
# the bootloader drive is successfully mounted, but something goes
# wrong during the upload process. They should be unreserved.

# NOTE:
# Do NOT flash firmware that does not respond to the 1200 baud protocol. These
# devices will not be able reflashed by the worker. Someone will have to go
# to the pico room, identify which device is broken, and press the button.
failed_serials = flasher.waitUntilFlashingFinished(timeout=60)

if failed_serials:
    raise Exception("Failed to flash.")

print("Device ready!")
