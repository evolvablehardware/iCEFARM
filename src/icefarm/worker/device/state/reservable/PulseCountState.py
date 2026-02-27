from __future__ import annotations
import re

from icefarm.worker.device.state.core import AbstractState, FlashState, UploadState
from icefarm.worker.device.state.reservable import reservable

@reservable("pulsecount")
class PulseCountStateFlasher(AbstractState):
    serial_patch = None

    def start(self):
        def parser(result: str):
            try:
                return re.search("pulses: ([0-9]+)", result).group(1)
            except:
                return None

        pulse_fac = lambda : UploadState(self.device, parser, self.config.pulse_firmware_path, patch_connect_serial=self.serial_patch)
        self.switch(lambda : FlashState(self.device, self.config.pulse_firmware_path, pulse_fac))

