import threading
import uuid
import re
from dataclasses import dataclass
import time
import os

import serial

from usbipice.worker.device import Device
from usbipice.worker.device.state.core import AbstractState, FlashState, BrokenState
from usbipice.worker.device.state.reservable import reservable
from usbipice.utils.dev import get_devs
#from  https://github.com/evolvablehardware/BitstreamEvolutionPico/blob/main/exampleProjectsC/bitstream_over_usb/bitstream_transfer_test.py
# TODO config file
PULSE_FIRMWARE_PATH = "examples/pulse_count_usbip/firmware/build/bitstream_over_usb.uf2"
BAUD = 115200            # ignored by TinyUSB but needed by pyserial
CHUNK_SIZE = 512         # bytes per write
INTER_CHUNK_DELAY = 0.00001  # seconds
BITSTREAM_SIZE = 0

@dataclass
class Bitstream:
    location: str
    name: str

@reservable("pulsecount")
class PulseCountStateFlasher(AbstractState):
    def start(self):
        pulse_fac = lambda : PulseCountState(self.getDevice())
        self.switch(lambda : FlashState(self.getDevice(), PULSE_FIRMWARE_PATH, pulse_fac))
class PulseCountState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.getNotif().sendDeviceInitialized(self.getSerial())

        self.cv = threading.Condition()
        self.bitstream_queue: list[Bitstream] = []
        # name -> pulses
        self.results = {}

        # ensure new ports show correctly
        time.sleep(2)
        paths = get_devs().get(self.getSerial())

        if not paths:
            self.switch(lambda : BrokenState(self.getDevice()))

        port = list(filter(lambda x : x.get("ID_USB_INTERFACE_NUM") == "00", paths))

        if not port:
            self.switch(lambda : BrokenState(self.getDevice()))

        port = port[0].get("DEVNAME")

        self.ser = serial.Serial(port, BAUD, timeout=0.1)
        self.reader = Reader(self.ser)
        self.sender = PulseCountEventSender(self.getDevice())

        self.exiting = False
        self.thread = threading.Thread(target=lambda : self.run())
        self.thread.start()

    @AbstractState.register("evaluate", "files")
    def queue(self, files):
        media_path = self.getDevice().getMediaPath()
        paths = [str(media_path.joinpath(str(uuid.uuid4()))) for _ in range(len(files))]

        for path, tmp in zip(paths, files.values()):
            with open(path, "wb") as f:
                f.write(tmp.read())
                f.flush()

        self.getLogger().debug(f"queued bitstreams: {list(files.keys())}")

        with self.cv:
            for path, name in zip(paths, files.keys()):
                self.bitstream_queue.append(Bitstream(path, name))

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

            self.getLogger().debug(f"evaluating bitstream {bitstream.name}")

            with open(bitstream.location, "rb") as f:
                data = f.read()

            data_len = len(data)

            self.reader.waitUntilReady()

            self.getLogger().debug(f"uploading bitstream {bitstream.name}")

            for i in range(0, data_len, CHUNK_SIZE):
                chunk = data[i:i+CHUNK_SIZE]
                self.ser.write(chunk)
                self.ser.flush()
                time.sleep(INTER_CHUNK_DELAY)

            self.getLogger().debug("waiting for pulse")

            result = self.reader.waitUntilPulse()

            self.getLogger().debug(f"got pulse: {result}")

            if result is False:
                with self.cv:
                    self.bitstream_queue.append(bitstream)
                    continue

            self.results[bitstream.name] = result
            os.remove(bitstream.location)

            with self.cv:
                if not self.bitstream_queue:
                    if not self.sender.finished(self.results):
                        self.getLogger().error("failed to send results")

                    self.results = {}

    def handleExit(self):
        self.exiting = True
        with self.cv:
            self.cv.notify_all()
        self.thread.join()
        self.reader.exit()
        self.ser.close()

class Reader:
    def __init__(self, port: serial.Serial):
        self.port = port
        self.cv = threading.Condition()
        self.ready = True
        self.last_pulse = None
        self.exiting = False

        self.thread = threading.Thread(target=lambda : self.read())
        self.thread.start()

    def read(self):
        while self.port.is_open and not self.exiting:
            data = self.port.read(self.port.in_waiting or 1)
            if not data:
                continue
            data = str(data)

            pulses = re.search("pulses: ([0-9]+)", data)
            if pulses:
                with self.cv:
                    self.last_pulse = pulses.group(1)
                    self.cv.notify_all()

            timeout = re.search("Watchdog timeout", data)
            if timeout:
                with self.cv:
                    self.last_pulse = False
                    self.cv.notify_all()

            wait = re.search("Waiting for bitstream transfer", data)
            if wait:
                with self.cv:
                    self.ready = True
                    self.cv.notify_all()

    def waitUntilReady(self):
        with self.cv:
            self.cv.wait_for(lambda : self.ready)
            self.ready = False

    def waitUntilPulse(self):
        with self.cv:
            self.cv.wait_for(lambda : self.last_pulse is not None or self.exiting)
            last_pulse = self.last_pulse
            self.last_pulse = None
            return last_pulse

    def exit(self):
        self.exiting = True
        with self.cv:
            self.cv.notify_all()
        self.thread.join()

class PulseCountEventSender:
    def __init__(self, device: Device):
        self.notif = device.getNotif()
        self.serial = device.getSerial()

    def finished(self, pulses):
        return self.notif.sendDeviceEvent(self.serial, {
            "event": "results",
            "serial": self.serial,
            "results": pulses
        })
