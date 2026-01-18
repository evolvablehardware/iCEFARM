import os
import logging
import sys
import time
import atexit
from pathlib import Path
import shutil
import threading
import math

from icefarm.client.drivers import PulseCountClient
from icefarm.client.lib.pulsecount import PulseCountEvaluation
from icefarm.utils import generate_circuit, batch

#################################################
# Whether to evaluate circuits on each pico, or distribute them evenly
EVALUATE_EACH = True
# Whether to log all data received from workers/control
EVENT_LOGGING = True
# Paths to bin circuits to evaluate.
# NOTE: Pulses are evaluated for 5 seconds, so results will differ from kHz
BITSTREAM_PATHS = ["examples/pulse_count_driver/precompiled_circuits/circuit_generated_2Khz.bin",
                   "examples/pulse_count_driver/precompiled_circuits/circuit_generated_8Khz.bin",
                   "examples/pulse_count_driver/precompiled_circuits/circuit_generated_32Khz.bin"
                   ]

# Target kHz of circuits. These circuits will be automatically generated, compiled, and evaluated.
# Usage requires yosys, nextpnr-ice40, and icepack. If you don't have these tools installed,
# set this to [] and it will be ignored.
# COMPILE_PULSES = [1, 2, 4, 16, 64]
COMPILE_PULSES = []

# Directory to build circuits in
BUILD_DIR = "examples/pulse_count_driver/build"

# If you have more than one device, feel free to increase this number. This
# particular client evaluates each circuit once on each of the devices,
# but the distribution method can be changed by modifying the client.
NUM_DEVICES = 1

# Whether to wait for devices to become available if
# not enough devices are available
WAIT_FOR_AVAILABLE = False
# How long to wait before timing out
AVAILABLE_S_TO_WAIT = 60

# ID for the client. Must be unique.
CLIENT_NAME = "read default example"

# Url to the control server.
CONTROL_SERVER = "http://localhost:8080"

if not (CONTROL_SERVER):
    CONTROL_SERVER = os.environ.get("USBIPICE_CONTROL_SERVER")
#################################################

if not CONTROL_SERVER:
    raise Exception("Configuration error")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

# Creates a client to interface with system
client = PulseCountClient(CONTROL_SERVER, CLIENT_NAME, logger, log_events=EVENT_LOGGING)

# This gracefully stops the client. It ends all devices that are reserved under
# its name. If the client does not gracefully exit, devices will still be reserved
# under its name. Reservations expire after about an hour, so this won't break a
# production environment, but it will cause devices to be unavailable for the remainder.
# If this happens, see the troubleshooting section of the README.
atexit.register(client.stop)

available = client.available()
logger.info(f"{available} available devices for reservation.")

# Reserves a device from the system. Since this is the pulse count client,
# the device will automatically be set to the pulse count device behavior.

logger.info("Reserving devices. This may take up to 30 seconds.")
devices = client.reserve(NUM_DEVICES, wait_for_available=WAIT_FOR_AVAILABLE, available_timeout=AVAILABLE_S_TO_WAIT)
if not devices:
    raise Exception("Failed to reserve any devices")

logger.info(f"Reserved devices: {devices}")

if len(devices) != NUM_DEVICES:
    raise Exception("Failed to reserve desired amount of devices")

# Builds circuits for target kHzs. This is not relevant
# to the iCEFARM system.
if COMPILE_PULSES:
    path = Path(BUILD_DIR)
    build_path = path.joinpath("build")
    out_path = path.joinpath("out")

    build_path.mkdir(parents=True, exist_ok=True)
    out_path.mkdir(parents=True, exist_ok=True)

    for khz in COMPILE_PULSES:
        new_location = str(out_path.joinpath(f"circuit_generated_{khz}kHz.bin"))
        if os.path.exists(new_location):
            logger.info(f"Circuit with {khz}kHz found in build location, using existing circuit.")
            BITSTREAM_PATHS.append(new_location)
            continue

        logger.info(f"Compiling target {khz}kHz circuit...")
        location, actual_khz = generate_circuit(khz * 1000, str(build_path))
        shutil.move(location, new_location)
        BITSTREAM_PATHS.append(new_location)
        logger.info(f"Circuit compiled with approximately {actual_khz:.2f}kHz.")

BITSTREAMS_PER_DEVICE = len(BITSTREAM_PATHS) / NUM_DEVICES
if EVALUATE_EACH:
    BITSTREAMS_PER_DEVICE *= NUM_DEVICES

# Raise exception if evaluation takes suspiciously long
def timeout():
    raise Exception("Watchdog timeout")
watchdog = threading.Timer(BITSTREAMS_PER_DEVICE * 20, timeout)
watchdog.daemon = True
watchdog.name = "watchdog-timeout"
watchdog.start()

evaluations = []

if EVALUATE_EACH:
    # Create a PulseCountEvaluation on all serials for each bitstream
    for bitstream in BITSTREAM_PATHS:
        evaluations.append(PulseCountEvaluation(devices, bitstream))
else:
    # Split bitstreams into batches
    batches = batch(BITSTREAM_PATHS, NUM_DEVICES)
    for serial, batches in zip(client.getSerials(), batches):
        # Assign a batch to each serial and create PulseCountEvaluations
        # for bitstreams in that batch
        for bitstream in batches:
            evaluations.append(PulseCountEvaluation([serial], bitstream))

if EVALUATE_EACH:
    logger.info(f"Expected wait time: {1.4 * BITSTREAMS_PER_DEVICE:.2f} seconds")
else:
    logger.info(f"Expected wait time: {1.4 * math.ceil(BITSTREAMS_PER_DEVICE):.2f} seconds")

logger.info("Sending bitstreams...")

start_time = time.time()

# Returns results as they come in
for serial, evaluation, result in client.evaluateEvaluations(evaluations):
    print(f"Serial {serial}, bitstream {evaluation.filepath}, result {result}")


elapsed = time.time() - start_time

print(f"Total elapsed evaluation time: {elapsed:.2f}")
print(f"Average circuit evaluation time: {elapsed / (BITSTREAMS_PER_DEVICE * NUM_DEVICES):.2f}")

print(f"Total latency: {elapsed - 1 * BITSTREAMS_PER_DEVICE:.2f}")
print(f"Average latency: {(elapsed / BITSTREAMS_PER_DEVICE) - 5:.2f}")
