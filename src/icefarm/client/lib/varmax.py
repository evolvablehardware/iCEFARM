from __future__ import annotations

from icefarm.client.lib import AbstractEventHandler, register, BaseClient
from icefarm.client.lib.BatchRequest import Evaluation

class VarMaxEvaluation(Evaluation):
    def __init__(self, serials, filepath):
        super().__init__(serials)
        self.filepath = filepath

class VarMaxEventHandler(AbstractEventHandler):
    @register("results", "batch_id", "serial", "results")
    # batch_id -> evaluation_id -> variance_fitness
    def results(self, serial: str, results: dict[str, dict[str, list]]):
        """Called when ALL bitstreams have been evaluated. Results maps
        from the evaluation id to the variance fitness value."""

class VarMaxBaseClient(BaseClient):
    """Provides access to variance maximization specific control API methods."""
    def reserve(self, amount, wait_for_available=False, available_timeout=60, kind="variance"):
        return super().reserve(amount, kind, {}, wait_for_available=wait_for_available, available_timeout=available_timeout)

    def reserveSpecific(self, serials: list[str], kind="variance"):
        return super().reserveSpecific(serials, kind, {})

    def evaluateBatch(self, batch_id: str, evaluations: list[VarMaxEvaluation]):
        """Sends a batch of VarMaxEvaluations to iCEFARM workers. The Evaluations must share
        the same set of serials."""
        if len(set([evaluation.serials for evaluation in evaluations])) != 1:
            raise Exception("VarMax evaluation commands contain different serials")

        files = {}
        for evaluation in evaluations:
            with open(evaluation.filepath, "rb") as f:
                files[evaluation.id] = f.read().decode("cp437")

        return self.requestBatchWorker(list(evaluations[0].serials), "evaluate", {
            "files": files,
            "batch_id": batch_id
        })
