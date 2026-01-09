from __future__ import annotations

from usbipice.client.lib import AbstractEventHandler, register, BaseClient
from usbipice.client.lib.BatchRequest import Evaluation

class PulseCountEvaluation(Evaluation):
    def __init__(self, serials, filepath):
        super().__init__(serials)
        self.filepath = filepath

class PulseCountEventHandler(AbstractEventHandler):
    @register("results", "batch_id", "serial", "results")
    # batch_id -> evaluation_id -> pulses
    def results(self, serial: str, results: dict[str, dict[str, list]]):
        """Called when ALL bitstreams have been evaluated. Results maps
        from the file parameter used in the request body to the
        pulse amount."""

class PulseCountBaseClient(BaseClient):
    def reserve(self, amount):
        return super().reserve(amount, "pulsecount", {})

    def evaluateBatch(self, batch_id: str, evaluations: list[PulseCountEvaluation]):
        """Evaluates a batch of PulseCountEvaluations. The Evaluations must share
        the same set of serials."""
        if len(set([evaluation.serials for evaluation in evaluations])) != 1:
            raise Exception("Pulsecount evaluation commands contain different serials")

        files = {}
        for evaluation in evaluations:
            with open(evaluation.filepath, "rb") as f:
                files[evaluation.id] = f.read().decode("cp437")

        # files -> [data, id]
        return self.requestBatchWorker(list(evaluations[0].serials), "evaluate", {
            "files": files,
            "batch_id": batch_id
        })
