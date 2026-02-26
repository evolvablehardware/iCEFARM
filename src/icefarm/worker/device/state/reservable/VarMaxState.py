from __future__ import annotations
import threading
import uuid
import re
from dataclasses import dataclass
import time
import os

import serial

from icefarm.worker.device.state.core import AbstractState, FlashState, BrokenState
from icefarm.worker.device.state.reservable import reservable
from icefarm.utils.dev import get_devs

import typing
if typing.TYPE_CHECKING:
    from icefarm.worker.device import Device

BAUD = 115200            # ignored by TinyUSB but needed by pyserial
CHUNK_SIZE = 512         # bytes per write
INTER_CHUNK_DELAY = 0.00001  # seconds


def calculate_variance(samples: list[int]) -> float:
    """Calculate variance fitness from ADC samples.
    Replicates VarMaxFitnessFunction.__measure_variance_fitness():
    sum of absolute differences between consecutive samples, divided by sample count.
    """
    if len(samples) < 2:
        return 0.0
    variance_sum = 0
    for i in range(len(samples) - 1):
        variance_sum += abs(samples[i + 1] - samples[i])
    return variance_sum / len(samples)


@dataclass
class Bitstream:
    location: str
    name: str
    batch_id: str


@reservable("variance")
class VarMaxStateFlasher(AbstractState):
    def start(self):
        varmax_fac = lambda: VarMaxState(self.device)
        self.switch(lambda: FlashState(self.device, self.config.variance_firmware_path, varmax_fac))


class VarMaxState(AbstractState):
    def __init__(self, state):
        super().__init__(state)

        self.cv = threading.Condition()
        self.bitstream_queue: list[Bitstream] = []
        # batch_id -> [(name, variance_fitness), ...]
        self.results = {}
        self.result_amount = 0
        self.flush_threshold = 4

        # ensure new ports show correctly
        time.sleep(2)

        self.ser = self.connectSerial()
        if self.ser is None:
            return
        self.reader = VarMaxReader(self.ser)
        self.sender = VarMaxEventSender(self.device_event_sender)

        self.exiting = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

        self.device_event_sender.sendDeviceInitialized()

    def connectSerial(self):
        paths = get_devs().get(self.serial)

        if not paths:
            self.switch(lambda: BrokenState(self.device))
            return None

        port = list(filter(lambda x: x.get("ID_USB_INTERFACE_NUM") == "00", paths))

        if not port:
            self.switch(lambda: BrokenState(self.device))
            return None

        port = port[0].get("DEVNAME")
        return serial.Serial(port, BAUD, timeout=0.1)

    @AbstractState.register("evaluate", "files", "batch_id")
    def queue(self, files, batch_id):
        media_path = self.device.media_path
        paths = [str(media_path.joinpath(str(uuid.uuid4()))) for _ in range(len(files))]

        for path, data in zip(paths, files.values()):
            with open(path, "wb") as f:
                f.write(data.encode("cp437"))
                f.flush()

        self.logger.debug(f"queued bitstreams: {list(files.keys())}")

        with self.cv:
            for path, name in zip(paths, files.keys()):
                self.bitstream_queue.append(Bitstream(path, name, batch_id))

            self.cv.notify_all()

        return True

    def run(self):
        time.sleep(2)

        while not self.exiting:
            with self.cv:
                if not self.bitstream_queue:
                    self.cv.wait_for(lambda: self.bitstream_queue or self.exiting)

                if self.exiting:
                    return

                bitstream = self.bitstream_queue.pop()

            self.logger.debug(f"evaluating bitstream {bitstream.name}")

            with open(bitstream.location, "rb") as f:
                data = f.read()

            data_len = len(data)

            self.reader.waitUntilReady()

            self.logger.debug(f"uploading bitstream {bitstream.name}")

            for i in range(0, data_len, CHUNK_SIZE):
                chunk = data[i:i+CHUNK_SIZE]
                self.ser.write(chunk)
                self.ser.flush()
                time.sleep(INTER_CHUNK_DELAY)

            self.logger.debug("waiting for ADC samples")

            samples = self.reader.waitUntilSamples()

            if samples is False:
                self.logger.debug("got timeout, re-queuing bitstream")
                with self.cv:
                    self.bitstream_queue.append(bitstream)
                    continue

            variance_fitness = calculate_variance(samples)
            self.logger.debug(f"got variance fitness: {variance_fitness} from {len(samples)} samples")

            if bitstream.batch_id not in self.results:
                self.results[bitstream.batch_id] = []

            self.results[bitstream.batch_id].append((bitstream.name, variance_fitness))
            self.result_amount += 1
            os.remove(bitstream.location)

            with self.cv:
                if not self.bitstream_queue or self.result_amount >= self.flush_threshold:
                    for batch_id, results in self.results.items():
                        if not self.sender.finished(batch_id, results):
                            self.logger.error("failed to send results")

                    self.results = {}
                    self.result_amount = 0

    def handleExit(self):
        self.exiting = True
        with self.cv:
            self.cv.notify_all()
        self.thread.join()
        self.reader.exit()
        self.ser.close()

    def reboot(self):
        self.switch(lambda: VarMaxStateFlasher(self.device))


class VarMaxReader:
    """Reads serial output from variance firmware and parses ADC sample data."""
    def __init__(self, port: serial.Serial):
        self.port = port
        self.cv = threading.Condition()
        self.ready = True
        self.last_samples = None
        self.exiting = False

        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        last_read = ""
        while True:
            while self.port.is_open and not self.exiting and "\\r\\n" not in last_read:
                if (data := self.port.read(self.port.in_waiting or 1)):
                    last_read += str(data)[2:-1]

            if "\\r\\n" not in last_read:
                break

            line = last_read[:last_read.index("\\r\\n")]
            last_read = last_read[last_read.index("\\r\\n") + 4:]

            # Parse "samples: v1,v2,v3,...,vN"
            samples_match = re.search(r"samples:\s*([\d,\s]+)", line)
            if samples_match:
                try:
                    sample_str = samples_match.group(1).strip()
                    samples = [int(s.strip()) for s in sample_str.split(",") if s.strip()]
                    with self.cv:
                        self.last_samples = samples
                        self.cv.notify_all()
                except ValueError:
                    pass

            timeout = re.search("Watchdog timeout", line)
            if timeout:
                with self.cv:
                    self.last_samples = False
                    self.cv.notify_all()

            wait = re.search("Waiting for bitstream transfer", line)
            if wait:
                with self.cv:
                    self.ready = True
                    self.cv.notify_all()

            if self.exiting:
                return

    def waitUntilReady(self):
        with self.cv:
            if not self.ready:
                self.cv.wait_for(lambda: self.ready)

            self.ready = False

    def waitUntilSamples(self):
        """Wait for ADC samples from firmware. Returns list[int] on success, False on timeout."""
        with self.cv:
            self.cv.wait_for(lambda: self.last_samples is not None or self.exiting)
            last_samples = self.last_samples
            self.last_samples = None
            return last_samples

    def exit(self):
        self.exiting = True
        with self.cv:
            self.cv.notify_all()
        self.thread.join()


class VarMaxEventSender:
    def __init__(self, event_sender):
        self.event_sender = event_sender

    def finished(self, batch_id, results):
        return self.event_sender.sendDeviceEvent("results", {
            "results": results,
            "batch_id": batch_id
        })
