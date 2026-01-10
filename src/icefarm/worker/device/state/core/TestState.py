import threading

from icefarm.worker.device.state.core import AbstractState, BrokenState, ReadyState
from icefarm.utils import check_default

class TestState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.lock = threading.Lock()
        self.exiting = False

        self.database.updateDeviceStatus(self.serial, "testing")

        self.timer = threading.Timer(30, lambda : self.switch(lambda : BrokenState(self.device)))
        self.timer.start()

    def handleAdd(self, dev):
        path = dev.get("DEVNAME")

        if not path:
            self.logger.warning("add event with no devname")
            return

        with self.lock:
            if self.exiting:
                return

            self.exiting = True

            if check_default(path):
                self.timer.cancel()
                self.switch(lambda : ReadyState(self.device))
