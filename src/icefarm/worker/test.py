import time
import logging
import sys
import os

import pyudev
from flask import Flask
from flask_socketio import SocketIO

from icefarm.worker import Config, device

from icefarm.utils import RemoteLogger
from icefarm.worker.app import create_app, MAX_REQUEST_SIZE
from icefarm.worker.device import DeviceManager, DeviceEventSender
from icefarm.worker.device.state.core import FlashState, TestState, ReadyState
from icefarm.worker.device.state.reservable import PulseCountState

BITSTREAM_LENGTH = 104000

class FakeType(type):
    def __getattribute__(cls, name):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return FakeObject()

class FakeObject(metaclass=FakeType):
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwds):
        return FakeObject()

    def __getattribute__(self, name):
        return FakeObject()

class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.data_length = 0
        self.in_waiting = 0
        self.is_open = True

        self.queue = ""

    def write(self, data):
        self.data_length += len(data)
        if self.data_length >= BITSTREAM_LENGTH:
            self.queue += "pulses: 12345\\r\\n"
            self.queue += "Waiting for bitstream transfer\\r\\n"

    def flush(self):
        pass

    def read(self, amount):
        if self.queue:
            msg = self.queue
            self.queue = ""
            return msg

        time.sleep(5)

    def close(self):
        pass

class FakeDevice:
    def __init__(self, properties):
        self.properties = properties

    def __iter__(self):
        return zip(self.properties.keys(), self.properties.values())

class FakeEventSender(DeviceEventSender):
    def __init__(self, event_sender, serial, logger):
        super().__init__(event_sender, serial, logger)
        self.events = []

    def sendDeviceEvent(self, contents):
        self.event_sender.append(contents)

def flash_state_start(self):
    """Replaces start during testing."""
    time.sleep(5)

    if self.timer:
        self.timer.cancel()
    self.switch(self.next_state_factory)

def test_state_start(self):
    if self.timer:
        self.timer.cancel()

    self.switch(lambda : ReadyState(self.device))

def patch(patch_event_sender=False):
    """Patches various modules to enable testing without hardware.
    - Disables pyudev events
    - Removes preexisting device scan from DeviceMonitor
    - FlashState succeeds after a few seconds and does not perform device interactions
    - TestState succeeds after a few seconds and does not perform device interactions
    - PulseCountState.ser: Serial is replaced with an emulation of the pulse count firmware
    """
    pyudev.Context = FakeObject
    pyudev.Monitor = FakeObject
    pyudev.MonitorObserver = FakeObject
    DeviceManager.scan = lambda self : None

    FlashState.start = flash_state_start
    FlashState.handleAdd = lambda self, dev : None
    TestState.start = test_state_start
    FlashState.handleAdd = lambda self, dev : None
    PulseCountState.connectSerial = lambda self : FakeSerial()

    if patch_event_sender:
        device.DeviceEventSender = FakeEventSender

def generate_device_add(serial):
    return FakeDevice({
        'CURRENT_TAGS': ':systemd:',
        'DEVLINKS': f'/dev/serial/by-path/pci-0000:00:14.0-usbv2-0:7:1.0 /dev/serial/by-path/pci-0000:00:14.0-usb-0:7:1.0 /dev/serial/by-id/usb-Raspberry_Pi_Pico_{serial}-if00',
        'DEVNAME': '/dev/ttyACM0',
        'DEVPATH': '/devices/pci0000:00/0000:00:14.0/usb1/1-7/1-7:1.0/tty/ttyACM0',
        'ID_BUS': 'usb',
        'ID_MM_CANDIDATE': '1',
        'ID_MODEL': 'Pico',
        'ID_MODEL_ENC': 'Pico',
        'ID_MODEL_ID': '0009',
        'ID_PATH': 'pci-0000:00:14.0-usb-0:7:1.0',
        'ID_PATH_TAG': 'pci-0000_00_14_0-usb-0_7_1_0',
        'ID_PATH_WITH_USB_REVISION': 'pci-0000:00:14.0-usbv2-0:7:1.0',
        'ID_REVISION': '0100',
        'ID_SERIAL': f'Raspberry_Pi_Pico_{serial}',
        'ID_SERIAL_SHORT': serial,
        'ID_TYPE': 'generic',
        'ID_USB_CLASS_FROM_DATABASE': 'Miscellaneous Device',
        'ID_USB_DRIVER': 'cdc_acm',
        'ID_USB_INTERFACES': ':020200:0a0000:',
        'ID_USB_INTERFACE_NUM': '00',
        'ID_USB_MODEL': 'Pico',
        'ID_USB_MODEL_ENC': 'Pico',
        'ID_USB_MODEL_ID': '0009',
        'ID_USB_PROTOCOL_FROM_DATABASE': 'Interface Association',
        'ID_USB_REVISION': '0100',
        'ID_USB_SERIAL': f'Raspberry_Pi_Pico_{serial}',
        'ID_USB_SERIAL_SHORT': serial,
        'ID_USB_TYPE': 'generic',
        'ID_USB_VENDOR': 'Raspberry_Pi',
        'ID_USB_VENDOR_ENC': 'Raspberry\\x20Pi',
        'ID_USB_VENDOR_ID': '2e8a',
        'ID_VENDOR': 'Raspberry_Pi',
        'ID_VENDOR_ENC': 'Raspberry\\x20Pi',
        'ID_VENDOR_ID': '2e8a',
        'MAJOR': '166',
        'MINOR': '0',
        'SUBSYSTEM': 'tty',
        'TAGS': ':systemd:',
        'USEC_INITIALIZED': '58315878783'
    })

def main():
    patch()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    config_path = os.environ.get("USBIPICE_WORKER_CONFIG")
    if not config_path:
        config_path = None
    config = Config(path=config_path)

    if config.control_server_url:
        logger = RemoteLogger(logger, config.control_server_url, config.worker_name)

    app = Flask(__name__)
    socketio = SocketIO(app, max_http_buffer_size=MAX_REQUEST_SIZE)
    manager = create_app(app, socketio, config, logger)

    manager.handleDevEvent("add", generate_device_add("1111111111111111"))
    manager.handleDevEvent("add", generate_device_add("2222222222222222"))
    manager.handleDevEvent("add", generate_device_add("3333333333333333"))
    manager.handleDevEvent("add", generate_device_add("4444444444444444"))

    socketio.run(app, port=config.server_port, allow_unsafe_werkzeug=True, host="0.0.0.0")

if __name__ == "__main__":
    main()
