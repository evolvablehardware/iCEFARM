from __future__ import annotations
import threading
from typing import Dict
from collections.abc import Generator

from usbipice.client.lib.pulsecount import PulseCountBaseClient, PulseCountEventHandler, PulseCountEvaluation
from usbipice.client.lib import register
from usbipice.client.lib.utils import LoggerEventHandler, ReservationExtender
from usbipice.client.lib.BatchRequest import BalancedBatchFactory, EvaluationBundle

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from usbipice.client.lib.BatchRequest import AbstractBatchFactory, Evaluation

class PulseCountClient(PulseCountBaseClient):
    def __init__(self, url, client_name, logger, log_events=False):
        super().__init__(url, client_name, logger)

        self.addEventHandler(ReservationExtender(self.server, self, logger))
        if log_events:
            self.addEventHandler(LoggerEventHandler(self.server, logger))

        self.batch_factories: dict[str, AbstractBatchFactory] = {}

        class ResultHandler(PulseCountEventHandler):
            def __init__(self, event_server, client: PulseCountClient):
                super().__init__(event_server)
                self.client = client

            @register("results", "batch_id", "serial", "results")
            def results(self, batch_id: str, serial: str, results: Dict[str, int]):
                factory = self.client.batch_factories.get(batch_id)
                if not factory:
                    return

                for uid, pulses in results:
                    factory.processResult(serial, uid, pulses)

        self.addEventHandler(ResultHandler(self.server, self))

    def evaluateFactory(self, factory: AbstractBatchFactory) -> Generator[tuple[str, Evaluation, dict]]:
        self.batch_factories[factory.bundle.id] = factory

        def evaluate_batches():
            for evaluations in factory.getBatches():
                # TODO not sure why super(type(self), self) doesn't work here
                for serial_group in evaluations.values():
                    PulseCountBaseClient.evaluateBatch(self, factory.bundle.id, serial_group)

        threading.Thread(target=evaluate_batches, name="batch-sender").start()

        for result in factory.getResults():
            yield result

        del self.batch_factories[factory.bundle.id]

    def evaluateEvaluations(self, evaluations: list[PulseCountEvaluation], batch_size=5):
        batch_factory = BalancedBatchFactory(EvaluationBundle(evaluations, batch_size))
        return self.evaluateFactory(batch_factory)

    def evaluateBitstreams(self, bitstreams, serials=None):
        if not serials:
            serials = self.getSerials()

        serials = set(serials)

        evaluations = [PulseCountEvaluation(serials, bitstream) for bitstream in bitstreams]
        for serial, evaluation, pulses in self.evaluateEvaluations(evaluations):
            yield serial, evaluation.filepath, pulses
