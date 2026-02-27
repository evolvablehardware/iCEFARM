from __future__ import annotations
import re
from icefarm.worker.device.state.core import AbstractState, FlashState, UploadState
from icefarm.worker.device.state.reservable import reservable

BAUD = 115200            # ignored by TinyUSB but needed by pyserial
CHUNK_SIZE = 512         # bytes per write
INTER_CHUNK_DELAY = 0.00001  # seconds

#TODO this in bitstreamevo
def calculate_variance(samples: list[int]) -> float:
    """Calculate variance fitness from ADC samples.
    Replicates VarMaxFitnessFunction.__measure_variance_fitness():
    sum of absolute differences between consecutive samples, divided by sample count.
    """
    if len(samples) < 2:
        return 0.0
    variance_sum = 0
    for i in range(len(samples) - 1):
        variance_sum += abs(samples[i + 1] - samples[i])
    return variance_sum / len(samples)

@reservable("variance")
class VarMaxStateFlasher(AbstractState):
    serial_patch = None

    def start(self):
        def parser(result: str):
            try:
                samples_match = re.search(r"samples:\s*([\d,\s]+)", result)
                sample_str = samples_match.group(1).strip()
                samples = [int(s.strip()) for s in sample_str.split(",") if s.strip()]
                return calculate_variance(samples)
            except:
                return None

        var_fac = lambda : UploadState(self.device, parser, self.config.variance_firmware_path, patch_connect_serial=self.serial_patch)
        self.switch(lambda : FlashState(self.device, self.config.variance_firmware_path, var_fac))
