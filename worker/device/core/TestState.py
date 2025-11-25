import threading

from worker.device.core import AbstractState
from worker.device.core import BrokenState
from worker.device.core import ReadyState

from utils.utils import check_default

class TestState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.lock = threading.Lock()
        self.exiting = False

        self.getDatabase().updateDeviceStatus(self.getSerial(), "testing")

    def handleAdd(self, dev):
        path = dev.get("DEVNAME")

        if not path:
            self.state.getLogger().warning("add event with no devname")
            return

        with self.lock:
            if self.exiting:
                return

            self.exiting = True

            if not check_default(path):
                self.state.getLogger().error("default firmware test failed")
                self.switch(lambda : BrokenState(self.getState()))
            else:
                self.switch(lambda : ReadyState(self.getState()))
