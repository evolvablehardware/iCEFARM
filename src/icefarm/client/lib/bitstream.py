
from __future__ import annotations
from typing import Generator
from icefarm.client.lib.BatchClient import Evaluation, BatchClient, Result

class BitstreamEvaluation(Evaluation):
    def __init__(self, serials, filepath):
        super().__init__(serials)
        self.filepath = filepath

    def _toJson(self):
        with open(self.filepath, "rb") as f:
            data = f.read()

        return {"files": {self.id: data}}

    def __str__(self):
        return f"<Serials: {self.serials}, filepath: {self.filepath}>"

class BitstreamBaseClient(BatchClient):
    """Provides access general bitstream evaluation API methods."""

    def reserve(self, devices: int | list[str], kind: str, extra_args={}, available_timeout=60, flush_interval_seconds: int=10, flush_at_bitstreams_remaining: int=25):
        args = {
            "flush_interval_seconds": flush_interval_seconds,
            "flush_at_bitstreams_remaining": flush_at_bitstreams_remaining
        }

        for k, v in extra_args.items():
            args[k] = v

        if isinstance(devices, list):
            # TODO support available_timeout here
            return super().reserveSpecific(devices, kind, args)

        elif isinstance(devices, int):
            return super().reserve(devices, kind, args, available_timeout=available_timeout)

        else:
            raise Exception(f"Invalid devices: {devices}")

    def evaluateBitstreams(self, bitstreams: list[str], serials=None) -> Generator[Result]:
        """Sends bitstream filepaths to be evaluated by iCEFARM. If serials are not specified, bitstreams
        are evaluated on each reserved device. Results are received as (serial, filepath, result)."""
        if not serials:
            serials = self.getSerials()

        serials = set(serials)

        evaluations = [BitstreamEvaluation(serials, bitstream) for bitstream in bitstreams]
        return self.evaluateEvaluations(evaluations)
