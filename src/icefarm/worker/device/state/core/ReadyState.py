from icefarm.worker.device.state.core import AbstractState

class ReadyState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.database.updateDeviceStatus(self.serial, "available")
