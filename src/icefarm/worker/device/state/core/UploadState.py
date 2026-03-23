import time
from logging import Logger, LoggerAdapter
import threading
import uuid
import re
from dataclasses import dataclass
import time
import os
from typing import Callable, Any, TYPE_CHECKING

import serial

from icefarm.worker.device.state.core import AbstractState, FlashState, BrokenState
from icefarm.utils import Queue, QueueShutDown, MappedQueues
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

class UploadLogger(LoggerAdapter):
    def __init__(self, logger: Logger, postfix: str, extra = None):
        super().__init__(logger, extra={})
        self.postfix = postfix

    def process(self, msg, kwargs):
        return f"{self.postfix} {msg}", kwargs

class UploadState(AbstractState):
    """
    State for evaluations that follow a common pattern:
    - Receive bitstreams from client
    - Upload bitstream, perform some calculations, print json formatted result
    - Send results to client
    """
    def __init__(self, state, parser: Callable[[str], Any], reboot_firmware_path, logger_postfix=None, flush_interval_seconds=None, flush_at_bitstreams_remaining=25):
        """
        Parameters:
        - parser: Function that parses output from device and returns parsed value, or None if no value was found
        - reboot_firmware_path: Firmware to flash when reboot function is called
        - logger_postfix: Optional string added before logger output. Intended to contain reservable name, as it would otherwise only show UploadState
        - flush_interval_seconds: Time between automatic result flushes, use 0 or None to disable
        - flush_at_bitstreams_remaining: Optionally flush once a low amount of bitstreams is received so that the client knows to send more. Note that flushes happen at 0 remaining regardless of this parameter.
        """
        super().__init__(state)
        if logger_postfix:
            self.logger = UploadLogger(self.logger, logger_postfix)

        self.parser = parser
        self.reboot_firmware_path = reboot_firmware_path
        self.bitstream_queue: Queue[Bitstream] = Queue()
        self.current_bitstream = None
        # name -> pulses
        self.results = MappedQueues()
        # TODO configurable by client
        self.flush_interval_seconds = flush_interval_seconds
        self.last_flush_time = time.time()
        self.flush_at_bitstreams_remaining = flush_at_bitstreams_remaining if flush_at_bitstreams_remaining else 0
        self.logger_postfix = logger_postfix
        self.ser = None
        self.reader = None
        self.sender = None
        self.thread = None

    def start(self):
        # ensure new ports show correctly
        # TODO this better
        time.sleep(2)

        self.ser = self.connectSerial()
        if self.ser is None:
            return
        self.reader = Reader(self.ser, self.parser, self.logger)
        self.sender = UploadEventSender(self.device_event_sender)

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
                f.write(data)
                f.flush()

        self.logger.debug(f"queued bitstreams: {list(files.keys())}")

        try:
            self.bitstream_queue.put(Bitstream(path, name, batch_id) for path, name in zip(paths, files.keys()))
        except QueueShutDown:
            # TODO inform client that this has happened, requires communication refactor first
            # as long as the client stops sending bitstreams before calling reboot this wont happen,
            # but if it does this is pretty bad
            self.logger.error(f"Received bitstreams after queue shutdown: {files.keys()}")

        return True

    def _writeBitstream(self, bitstream: Bitstream):
        """Read bitstream file, wait until device ready, write bitstream."""
        with open(bitstream.location, "rb") as f:
            data = f.read()

        data_len = len(data)

        self.reader.waitUntilReady()

        for i in range(0, data_len, CHUNK_SIZE):
            chunk = data[i:i+CHUNK_SIZE]
            self.ser.write(chunk)
            self.ser.flush()
            time.sleep(INTER_CHUNK_DELAY)

    def _flush(self):
        """"""
        try:
            flush_amount_ready = not self.bitstream_queue or len(self.bitstream_queue) == self.flush_at_bitstreams_remaining
        except QueueShutDown:
            return False
        flush_interval_ready = self.flush_interval_seconds and self.last_flush_time + self.flush_interval_seconds <= time.time()

        if not flush_amount_ready and not flush_interval_ready:
            return False

        if not self.sender.finished(self.results):
            self.logger.error("failed to send results")
            return False

        self.results = MappedQueues()
        self.last_flush_time = time.time()

        return True

    def run(self):
        time.sleep(2)

        while True:
            try:
                self.current_bitstream = self.bitstream_queue.pop()
            except QueueShutDown:
                return

            self.logger.debug(f"uploading bitstream {self.current_bitstream.name}")

            try:
                self._writeBitstream(self.current_bitstream)
            except Exception:
                self.reboot()
                return

            self.logger.debug("waiting for result")

            try:
                result = self.reader.waitUntilPulse()
            except Exception:
                self.reboot()
                return

            self.logger.debug(f"got result: {result}")

            self.results.append(self.current_bitstream.batch_id, (self.current_bitstream.name, result))
            os.remove(self.current_bitstream.location)
            self.current_bitstream = None

            self._flush()

    def handleExit(self):
        self.bitstream_queue.shutdown()

        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join()
        if self.reader:
            self.reader.exit()
        if self.ser and self.ser.is_open:
            self.ser.close()

    def reboot(self):
        # TODO kinda hacky
        # i don't like having to chain state switches but its better than
        # needing separate flash stuff
        bitstreams = self.bitstream_queue.shutdown()
        if self.current_bitstream:
            bitstreams.append(self.current_bitstream)

        def transfer_bitstreams():
            state = UploadState(self.device, self.parser, self.reboot_firmware_path, logger_postfix=self.logger_postfix, flush_at_bitstreams_remaining=self.flush_at_bitstreams_remaining, flush_interval_seconds=self.flush_interval_seconds)
            state.results = self.results
            state.bitstream_queue = Queue(bitstreams)
            return state

        self.handleExit()
        flasher = lambda : FlashState(self.device, self.reboot_firmware_path, transfer_bitstreams)
        self.switch(flasher)
class Reader:
    def __init__(self, port: serial.Serial, parser: Callable[[str], Any], logger):
        self.port = port
        self.parser = parser
        self.cv = threading.Condition()
        self.ready = True
        self.last_result = None
        self.exiting = False
        self.logger = logger

        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        last_read = ""
        while True:
            try:
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

            except Exception as e:
                # TODO handle this better
                self.logger.error(f"Exception during read: {e}")
                self.last_result = False
                with self.cv:
                    self.cv.notify_all()
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
            if last_result is False:
                raise Exception()
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

    def finished(self, results: MappedQueues):
        results = results.state
        events = [("results", {"results": pulses, "batch_id": batch_id}) for batch_id, pulses in results.items()]
        return self.event_sender.sendDeviceEvents(events)
