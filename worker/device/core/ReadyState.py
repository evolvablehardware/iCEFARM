from worker.device.core import AbstractState

class ReadyState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.getDatabase().updateDeviceStatus(self.getSerial(), "available")
