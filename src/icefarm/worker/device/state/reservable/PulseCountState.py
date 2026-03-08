from __future__ import annotations
import re

from icefarm.worker.device.state.core import AbstractState, FlashState, UploadState
from icefarm.worker.device.state.reservable import reservable

@reservable("pulsecount", "flush_interval_seconds", "flush_at_bitstreams_remaining")
class PulseCountStateFlasher(AbstractState):
    def __init__(self, device, flush_interval_seconds, flush_at_bitstreams_remaining):
        super().__init__(device)
        self.flush_interval_seconds = int(flush_interval_seconds)
        self.flush_at_bitstreams_remaining = int(flush_at_bitstreams_remaining)

    def start(self):
        def parser(result: str):
            try:
                return re.search("pulses: ([0-9]+)", result).group(1)
            except:
                return None

        pulse_fac = lambda : UploadState(self.device, parser, self.config.pulse_firmware_path, logger_postfix="(PulseCount)", flush_at_bitstreams_remaining=self.flush_at_bitstreams_remaining, flush_interval_seconds=self.flush_interval_seconds)
        self.switch(lambda : FlashState(self.device, self.config.pulse_firmware_path, pulse_fac))

