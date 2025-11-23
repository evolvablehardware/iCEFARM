import atexit

from client.FirmwareFlasher import FirmwareFlasher
from utils.dev import get_dev_paths

#################################################
# ID_SERIAL_SHORT field from udevadm info
# leave blank for auto
PICO_SERIAL = ""
FIRMWARE_PATH = ""
#################################################

# Find serial of connected device if one is not specified.
# get_dev_paths returns a dictionary mapping pico serials to lists
# of their device paths.
if not PICO_SERIAL:
    serials = list(get_dev_paths().keys())
    if not serials:
        raise Exception("Did not find any pico2ice devices.")

    if len(serials) != 1:
        raise Exception(f"Found multiple pico2ice devices. Please specify one. Serials: {serials}.")

    PICO_SERIAL = serials[0]

if not FIRMWARE_PATH:
    raise Exception("Firmware path not specified.")

print(f"Flashing to serial {PICO_SERIAL}...")

flasher = FirmwareFlasher()
# Start monitoring for device events.
flasher.startFlasher()
atexit.register(flasher.stopFlasher)
# Add to pool of devices to flash to. This
# does not wait to return until the device is
# flashed.
flasher.flash(PICO_SERIAL, FIRMWARE_PATH)
# Returns once all firmware is flashed, the timeout is reached, or stopFlasher is called.
# Remaining serials are still being flashed to, they just are not finished yet. However,
# they may be in a stalled state such as if the current firmware does not respond to the baud
# 1200 protocol. The failed serials indicate something went wrong during the transfer of the uf2 file.
remaining_serials, failed_serials = flasher.waitUntilFlashingFinished(timeout=60)
if remaining_serials:
    raise Exception("Firmware did not flash in time.")
if failed_serials:
    raise Exception("Firmware failed to upload.")

print("Success!")