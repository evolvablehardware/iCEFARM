import logging
import sys
import time
import atexit
import threading

from usbipice.client.drivers import PulseCountClient

#################################################
# Whether to log all data received from workers/control
EVENT_LOGGING = True
# Paths to bin circuits to evaluate.
# NOTE: Pulses are evaluated for 5 seconds, so results will differ from kHz
BITSTREAM_PATHS = ["examples/pulse_count_driver/precompiled_circuits/circuit_generated_2Khz.bin",
                   "examples/pulse_count_driver/precompiled_circuits/circuit_generated_8Khz.bin",
                   "examples/pulse_count_driver/precompiled_circuits/circuit_generated_32Khz.bin"
                   ]

NUM_DEVICES = 2
CLIENT_NAME = "pulse count tester"
CONTROL_SERVER = "http://control:8080"
#################################################
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

NUM_BITSTREAMS = len(BITSTREAM_PATHS)

client = PulseCountClient(CONTROL_SERVER, CLIENT_NAME, logger, log_events=EVENT_LOGGING)

atexit.register(client.stop)

logger.info("Reserving devices...")
devices = client.reserve(NUM_DEVICES)
if not devices:
    raise Exception("Failed to reserve any devices")

logger.info(f"Reserved devices: {devices}")

if len(devices) != NUM_DEVICES:
    raise Exception("Failed to reserve desired amount of devices")

def timeout():
    raise Exception("Watchdog timeout")
watchdog = threading.Timer(NUM_BITSTREAMS * 20, timeout)
watchdog.daemon = True
watchdog.name = "watchdog-timeout"
watchdog.start()

start_time = time.time()

# Returns dictionary mapping device_serial -> {file_path -> pulses}
pulses = client.evaluateEach(BITSTREAM_PATHS)
if not pulses:
    raise Exception("Did not receive any pulses")

elapsed = time.time() - start_time

print(f"Total elapsed evaluation time: {elapsed:.2f}")
print(f"Average circuit evaluation time: {elapsed / NUM_BITSTREAMS:.2f}")
# Pulse count firmware spends 5s per evaluation
print(f"Total latency: {elapsed - 5 * NUM_BITSTREAMS:.2f}")
print(f"Average latency: {(elapsed / NUM_BITSTREAMS) - 5:.2f}")
# Assumes 0.15s upload time
print(f"Total iCEFARM latency: {elapsed - 5.15 * NUM_BITSTREAMS:.2f}")
print(f"Average iCEFARM latency: {(elapsed / NUM_BITSTREAMS) - 5.15:.2f}")

for path in BITSTREAM_PATHS:
    print(f"Circuit {path}:")
    for serial in pulses:
        print(f"\tDevice {serial}: {pulses[serial][path]}")
