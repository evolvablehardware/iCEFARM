import threading

from usbipice.worker.device.state.core import AbstractState, BrokenState, ReadyState
from usbipice.utils import check_default

class TestState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.lock = threading.Lock()
        self.exiting = False

        self.getDatabase().updateDeviceStatus(self.getSerial(), "testing")

    def handleAdd(self, dev):
        path = dev.get("DEVNAME")

        if not path:
            self.getLogger().warning("add event with no devname")
            return

        with self.lock:
            if self.exiting:
                return

            self.exiting = True

            if not check_default(path):
                self.getLogger().error("default firmware test failed")
                self.switch(lambda : BrokenState(self.getDevice()))
            else:
                self.switch(lambda : ReadyState(self.getDevice()))
