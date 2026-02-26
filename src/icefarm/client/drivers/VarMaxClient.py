from __future__ import annotations
import threading
from typing import Dict
from collections.abc import Generator

from icefarm.client.lib.varmax import VarMaxBaseClient, VarMaxEventHandler, VarMaxEvaluation
from icefarm.client.lib import register
from icefarm.client.lib.utils import LoggerEventHandler, ReservationExtender
from icefarm.client.lib.BatchRequest import BalancedBatchFactory, EvaluationBundle

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from icefarm.client.lib.BatchRequest import AbstractBatchFactory, Evaluation

class VarMaxClient(VarMaxBaseClient):
    """Main client for variance maximization experiments."""
    def __init__(self, url, client_name, logger, log_events=False):
        super().__init__(url, client_name, logger)

        self.addEventHandler(ReservationExtender(self.server, self, logger))
        if log_events:
            self.addEventHandler(LoggerEventHandler(self.server, logger))

        self.batch_factories: dict[str, AbstractBatchFactory] = {}

        class ResultHandler(VarMaxEventHandler):
            """Receives and processes results of variance evaluations."""
            def __init__(self, event_server, client: VarMaxClient):
                super().__init__(event_server)
                self.client = client

            @register("results", "batch_id", "serial", "results")
            def results(self, batch_id: str, serial: str, results: Dict[str, float]):
                factory = self.client.batch_factories.get(batch_id)
                if not factory:
                    return

                for uid, value in results:
                    factory.processResult(serial, uid, value)

        self.addEventHandler(ResultHandler(self.server, self))

    def evaluateFactory(self, factory: AbstractBatchFactory) -> Generator[tuple[str, Evaluation, float]]:
        self.batch_factories[factory.bundle.id] = factory

        def evaluate_batches():
            for evaluations in factory.getBatches():
                for serial_group in evaluations.values():
                    self.evaluateBatch(factory.bundle.id, serial_group)

        threading.Thread(target=evaluate_batches, name="batch-sender").start()

        for result in factory.getResults():
            yield result

        del self.batch_factories[factory.bundle.id]

    def evaluateEvaluations(self, evaluations: list[VarMaxEvaluation], batch_size=5) -> Generator[tuple[str, Evaluation, float]]:
        return self.evaluateFactory(BalancedBatchFactory(EvaluationBundle(evaluations, batch_size)))

    def evaluateBitstreams(self, bitstreams: list[str], serials=None) -> Generator[tuple[str, str, float]]:
        """Sends bitstream filepaths to be evaluated by iCEFARM. If serials are not specified, bitstreams
        are evaluated on each reserved device. Results are received as (serial, filepath, variance_fitness)."""
        if not serials:
            serials = self.getSerials()

        serials = set(serials)

        evaluations = [VarMaxEvaluation(serials, bitstream) for bitstream in bitstreams]
        for serial, evaluation, value in self.evaluateEvaluations(evaluations):
            yield serial, evaluation.filepath, value
