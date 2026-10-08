import threading

from icefarm.worker.device.state.core import AbstractState, BrokenState, ReadyState
from icefarm.utils import check_default

class TestState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.lock = threading.Lock()
        self.exiting = False

        try:
            self.database.updateDeviceStatus(self.serial, "testing")
        except Exception:
            self.logger.error("failed to update device status in database to testing")

        self.timer = threading.Timer(30, lambda : self.switch(lambda : BrokenState(self.device)))
        self.timer.daemon = True
        self.timer.name = f"{self.serial}-test-timeout"
        self.timer.start()

    def handleAdd(self, dev):
        # TODO need to scan for ACM devices in addition to this? I believe its technically possible for the
        # dev file to be added before the state change but very unlikely as the pico needs to fully reboot
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
