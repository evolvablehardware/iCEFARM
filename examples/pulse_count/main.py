import logging
import sys
import os
import atexit
import time
import threading
import re
import subprocess
from enum import Enum, auto

import serial

from client.Client import Client
from client.EventHandler import DefaultEventHandler
from client.TimeoutDetector import TimeoutDetector
from client.FirmwareFlasher import FirmwareFlasher

from utils.utils import get_ip
from utils.dev import get_devs

# ==============================
# Configuration
# ==============================
BAUD = 115200            # ignored by TinyUSB but needed by pyserial
CHUNK_SIZE = 512         # bytes per write
INTER_CHUNK_DELAY = 0.00001  # seconds
SHOW_RX = True           # logger.info incoming text from device

CLIENT_NAME = "pulse count example"
CLIENT_IP = get_ip() # local network ip - must be accessible by control/worker servers
CLIENT_PORT = "8080"
CONTROL_SERVER = ""

CLK = 48000000           # clk hz firmware uses for ice40
TARGET_KHZ = [8, 16, 32, 64, 128]
FIRMWARE_PATH = "examples/pulse_count/firmware/build/bitstream_over_usb.uf2"
PCF_PATH = "examples/pulse_count/pico_ice.pcf"
BUILD_DIR = "examples/pulse_count/build"

if not CONTROL_SERVER:
    CONTROL_SERVER = os.environ.get("USBIPICE_CONTROL_SERVER")
# ==============================


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

def make(hz):
    """Produces a clock of approximately hz Hz on ICE_27 and
    writes bitstream to build/top.bin."""
    if not os.path.isdir("build"):
        os.mkdir("build")

    incr = int((CLK/hz) - 1)
    logger.info(f"Using {CLK / incr /1000:.2f} kHz.")
    veri = f"""
    module top (
        input CLK,
        output ICE_27,
        output LED_R,
        output LED_B
    );
    reg [22:0] counter;
    reg out;
    always @(posedge CLK) begin
        counter <= counter + 1;

        if (counter >= {incr}) begin
            out <= 1'b1;
            counter <= 23'b00000000000000000000000;
        end else begin
            out <= 1'b0;
        end
    end

    assign ICE_27 = out;
    assign LED_R = counter[22];
    endmodule
    """

    with open(os.path.join(BUILD_DIR, "top.v"), "w") as f:
        f.write(veri)

    subprocess.run(["bash", "examples/pulse_count/build.sh", BUILD_DIR, PCF_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    logger.info("Built.")

class Status(Enum):
    UPLOAD = auto()
    DONE = auto()
    FAILED = auto()

ready = True
cv = threading.Condition()
state = Status.UPLOAD

def read_from_device(ser: serial.Serial):
    """Thread that continuously reads from the Pico and logger.infos output."""
    global state
    global ready

    while ser.is_open:
        try:
            data = ser.read(ser.in_waiting or 1)
            if data:
                # logger.info raw text to stdout (decode safely)
                if SHOW_RX:
                    sys.stdout.write(data.decode(errors='replace'))
                    sys.stdout.flush()

                wait = re.search("Waiting for bitstream transfer", str(data))
                if wait:
                    with cv:
                        logger.info("setting ready")
                        ready = True
                        cv.notify_all()

                pulses = re.search("pulses: ([0-9]*)", str(data))
                if pulses:
                    logger.info(f"Got pulses: {pulses.group(1)}")

                    with cv:
                        logger.info("setting done")
                        state = Status.DONE
                        cv.notify_all()

                timeout = re.search("Watchdog timeout", str(data))
                if timeout:
                    with cv:
                        logger.info("setting failed")
                        state = Status.FAILED
                        cv.notify_all()


        except serial.SerialException:
            break
        except OSError:
            break

def transfer(ser: serial.Serial):
    logger.info("Starting transfer...")

    with open(os.path.join(BUILD_DIR, "top.bin"), "rb") as f:
        data = f.read()
    data_len = len(data)
    logger.info(f"File size: {data_len} bytes")

    # Send the file in chunks
    for i in range(0, data_len, CHUNK_SIZE):
        chunk = data[i:i+CHUNK_SIZE]
        ser.write(chunk)
        ser.flush()
        time.sleep(INTER_CHUNK_DELAY)

    logger.info("\nTransfer complete. Waiting for device response...")

client = Client(CLIENT_NAME, CONTROL_SERVER, logger)

event_handlers = [DefaultEventHandler(logger), TimeoutDetector(client, logger)]
client.startEventServer(event_handlers, CLIENT_IP, CLIENT_PORT)

pico_serials = client.reserve(1)

flasher = FirmwareFlasher()

def onexit():
    client.stopEventServer()
    client.endAll()
    flasher.stopFlasher()

atexit.register(onexit)

if not pico_serials:
    raise Exception("Failed to reserve a device.")
pico_serial = pico_serials[0]

flasher.startFlasher()
flasher.flash(pico_serial, FIRMWARE_PATH)
remaining_serials, failed_serials = flasher.waitUntilFlashingFinished(timeout=120)

if remaining_serials or failed_serials:
    raise Exception("Failed to flash.")

logger.info("Device ready!")
flasher.stopFlasher()

# Ensure device is connected
time.sleep(5)

paths = get_devs()

if pico_serial not in paths:
    raise Exception("Failed to find dev path.")

# Find correct interface
port = list(filter(lambda x : x.get("ID_USB_INTERFACE_NUM") == "00", paths[pico_serial]))

if not port:
    raise Exception("Failed to find cdc0.")

port = port[0].get("DEVNAME")

ser = serial.Serial(port, BAUD, timeout=0.1)
time.sleep(2)  # give Pico time to enumerate and reset

# Start background thread for reading device output
reader_thread = threading.Thread(target=read_from_device, args=(ser,), daemon=True)
reader_thread.start()

i = 0
while i < len(TARGET_KHZ):
    hz = TARGET_KHZ[i] * 1000
    make(hz)

    with cv:
        if not ready:
            cv.wait_for(lambda : ready)
        ready = False

    transfer(ser)
    logger.info("transfer done")

    with cv:
        if state not in [Status.DONE, Status.FAILED]:
            cv.wait_for(lambda : state in [Status.DONE, Status.FAILED] or ready)

        if state == Status.DONE:
            i += 1

        state = Status.UPLOAD


logger.info("Done!")
client.stopEventServer()
