import threading
import uuid
import re
from dataclasses import dataclass
import time
import os
from typing import Callable, Any, TYPE_CHECKING

import serial

from icefarm.worker.device.state.core import AbstractState, FlashState, BrokenState
from icefarm.utils.dev import get_devs

if TYPE_CHECKING:
    from icefarm.worker.device import Device

BAUD = 115200            # ignored by TinyUSB but needed by pyserial
CHUNK_SIZE = 512         # bytes per write
INTER_CHUNK_DELAY = 0.00001  # seconds
BITSTREAM_SIZE = 0 #TODO

@dataclass
class Bitstream:
    location: str
    name: str
    batch_id: str

class UploadState(AbstractState):
    """
    State for evaluations that follow a common pattern:
    - Receive bitstreams from client
    - Upload bitstream, perform some calculations, print json formatted result
    - Send results to client
    """
    def __init__(self, state, parser: Callable[[str], Any], reboot_firmware_path, patch_connect_serial=None):
        """
        Parser is a function that takes the incoming string output from the firmware and returns
        a parsed result, or None. Reboot_firmware_path is the firmware switched to when reboot called.
        """
        super().__init__(state)

        # this is an abomination but it needs to be patched differently for pulsecount and varmax...
        if patch_connect_serial:
            self.connectSerial = patch_connect_serial

        self.reboot_firmware_path = reboot_firmware_path
        self.cv = threading.Condition()
        self.bitstream_queue: list[Bitstream] = []
        # name -> pulses
        self.results = {}
        self.result_amount = 0
        # TODO configurable by client
        self.flush_threshold = 4

        # ensure new ports show correctly
        time.sleep(2)

        self.ser = self.connectSerial()
        if self.ser is None:
            return
        self.reader = Reader(self.ser, parser)
        self.sender = UploadEventSender(self.device_event_sender)

        self.exiting = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

        self.device_event_sender.sendDeviceInitialized()

    def connectSerial(self, max_retries=5, retry_delay=2):
        for attempt in range(max_retries):
            paths = get_devs().get(self.serial)

            if paths:
                port = list(filter(lambda x: x.get("ID_USB_INTERFACE_NUM") == "00", paths))
                if port:
                    port = port[0].get("DEVNAME")
                    return serial.Serial(port, BAUD, timeout=0.1)

            self.logger.debug(f"serial port not found, retrying ({attempt + 1}/{max_retries})")
            time.sleep(retry_delay)

        self.logger.error("serial port not found after retries")
        self.switch(lambda: BrokenState(self.device))
        return None

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
                    self.cv.wait_for(lambda : self.bitstream_queue or self.exiting)

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

            self.logger.debug("waiting for pulse")

            result = self.reader.waitUntilPulse()

            self.logger.debug(f"got pulse: {result}")

            if result is False:
                with self.cv:
                    self.bitstream_queue.append(bitstream)
                    continue

            if bitstream.batch_id not in self.results:
                self.results[bitstream.batch_id] = []

            self.results[bitstream.batch_id].append((bitstream.name, result))
            self.result_amount += 1
            os.remove(bitstream.location)

            with self.cv:
                if not self.bitstream_queue or self.result_amount >= self.flush_threshold:
                    for batch_id, pulses in self.results.items():
                        if not self.sender.finished(batch_id, pulses):
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
        clone = lambda : UploadState(self.device, self.parser)
        flasher = lambda : FlashState(clone, self.reboot_firmware_path, clone)
        self.switch(flasher)

class Reader:
    def __init__(self, port: serial.Serial, parser: Callable[[str], Any]):
        self.port = port
        self.parser = parser
        self.cv = threading.Condition()
        self.ready = True
        self.last_result = None
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

            results = self.parser(line)
            if results:
                with self.cv:
                    self.last_result = results
                    self.cv.notify_all()

            timeout = re.search("Watchdog timeout", line)
            if timeout:
                with self.cv:
                    self.last_result = False
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
                self.cv.wait_for(lambda : self.ready)

            self.ready = False

    def waitUntilPulse(self):
        with self.cv:
            self.cv.wait_for(lambda : self.last_result is not None or self.exiting)
            last_result = self.last_result
            self.last_result = None
            return last_result

    def exit(self):
        self.exiting = True
        with self.cv:
            self.cv.notify_all()
        self.thread.join()

class UploadEventSender:
    def __init__(self, event_sender):
        self.event_sender = event_sender

    def finished(self, batch_id, results):
        return self.event_sender.sendDeviceEvent("results", {
            "results": results,
            "batch_id": batch_id
        })
