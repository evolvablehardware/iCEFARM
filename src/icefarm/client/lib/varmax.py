from __future__ import annotations
from typing import Generator

from icefarm.client.lib.BatchClient import Evaluation, BatchClient

class VarMaxEvaluation(Evaluation):
    def __init__(self, serials, filepath):
        super().__init__(serials)
        self.filepath = filepath

    def _toJson(self):
        with open(self.filepath, "rb") as f:
            data = f.read()

        return {"files": {self.id: data}}

class VarMaxBaseClient(BatchClient):
    """Provides access to variance maximization specific control API methods."""
    def reserve(self, amount, wait_for_available=False, available_timeout=60, kind="variance", send_waveform=False, flush_interval_seconds=10, flush_at_bitstreams_remaining=25):
        args = {
            "send_waveform": send_waveform,
            "flush_interval_seconds": flush_interval_seconds,
            "flush_at_bitstreams_remaining": flush_at_bitstreams_remaining
        }
        return super().reserve(amount, kind, args, wait_for_available=wait_for_available, available_timeout=available_timeout)

    def reserveSpecific(self, serials: list[str], kind="variance", send_waveform=False, flush_interval_seconds=10, flush_at_bitstreams_remaining=25):
        args = {
            "send_waveform": send_waveform,
            "flush_interval_seconds": flush_interval_seconds,
            "flush_at_bitstreams_remaining": flush_at_bitstreams_remaining
        }
        return super().reserveSpecific(serials, kind, args or {})

    def evaluateBitstreams(self, bitstreams: list[str], serials=None) -> Generator[tuple[str, str, float]]:
        """Sends bitstream filepaths to be evaluated by iCEFARM. If serials are not specified, bitstreams
        are evaluated on each reserved device. Results are received as (serial, filepath, fitness)."""
        if not serials:
            serials = self.getSerials()

        serials = set(serials)

        evaluations = [VarMaxEvaluation(serials, bitstream) for bitstream in bitstreams]
        for serial, evaluation, fitness in self.evaluateEvaluations(evaluations):
            yield serial, evaluation.filepath, fitness
