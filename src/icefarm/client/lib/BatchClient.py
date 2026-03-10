from __future__ import annotations
import uuid
import threading
import math
from collections import Counter
from collections.abc import Generator
from abc import ABC, abstractmethod
from typing import Any, List, Dict

from icefarm.utils import MappedQueues
from icefarm.client.lib import BaseClient
from icefarm.client.lib.AbstractEventHandler import AbstractEventHandler, register

class Evaluation(ABC):
    """
    Circuit evaluation to be sent to the worker. Note that providing
    multiple serials to one Evaluation will result in faster evaluations than
    providing multiple Evaluations of the same bitstream.
    """
    def __init__(self, serials: set[str]):
        if not serials:
            raise Exception("Serials cannot be empty")

        self.serials = frozenset(serials)
        self.id = str(uuid.uuid4())

    def __eq__(self, other):
        return self.id  == other.id

    def __hash__(self):
        return hash(self.id)

    def toJson(self, batch_id: str) -> dict:
        json = self._toJson()
        json["batch_id"] = batch_id
        return json

    @abstractmethod
    def _toJson(self) -> Any:
        """Converts evaluation into json request for worker"""

class EvaluationBundle:
    """
    Bundles Evaluations into efficient batches that can be sent gradually rather than
    all at once.
    """
    def __init__(self, evaluations: list[Evaluation], batch_size):
        self.queue = MappedQueues()
        for evaluation in evaluations:
            self.queue.append(evaluation.serials, evaluation)

        self.evaluation_lookup = {evaluation.id : evaluation for evaluation in evaluations}

        self.batch_size = batch_size

        self.empty = False
        self.id = str(uuid.uuid4())

    def __next__(self) -> dict[set[str], list[Evaluation]]:
        """
        Produces the next batch. Batches are produced so that each Evaluation with multiple serials are sent in the same batch
        and the maximum evaluations are sent without exceeding the batch size amount of circuits for any serial.
        """
        serial_amounts = Counter()
        batch = {}

        search_order = sorted(self.queue.keys(), key=len)
        for serials in search_order:
            slots = min(self.batch_size - serial_amounts[serial] for serial in serials)
            if not slots:
                continue

            commands = self.queue.pop(serials, slots)
            batch[serials] = commands
            for serial in serials:
                serial_amounts[serial] += len(commands)

        if not batch:
            self.empty = True
            raise StopIteration

        return batch

    def __iter__(self):
        return self

class AbstractBatchFactory(ABC):
    """
    Produces batches for client consumption.
    """
    # this could be easily replaced with a bundle, not needed and complicated for now
    def __init__(self, evaluations: list[Evaluation], batch_size: int):
        super().__init__()
        self.bundle = EvaluationBundle(evaluations, batch_size=batch_size)
        self.results: list[tuple[Evaluation, dict]] = []
        self.result_cv = threading.Condition()

        self.awaiting_results: dict[str, set] = {}

    def processResult(self, serial: str, evaluation_id: str, result: Any):
        with self.result_cv:
            if serial not in self.awaiting_results:
                return

            if evaluation_id not in self.awaiting_results[serial]:
                return

            self.awaiting_results[serial] -= {evaluation_id}
            self.results.append((serial, evaluation_id, result))
            self.result_cv.notify_all()

    def getResults(self) -> Generator[tuple[str, Evaluation, Any]]:
        """Produces results as they received by processResult."""
        while True:
            with self.result_cv:
                if not self.results:
                    self.result_cv.wait_for(lambda : self.results)

                for serial, evaluation_id, result in self.results:
                    evaluation = self.bundle.evaluation_lookup.get(evaluation_id)
                    yield serial, evaluation, result

                self.results = []

                if self.bundle.empty and not any(self.awaiting_results.values()):
                    return

    def _addBatch(self, batch: dict[set[str], list[Evaluation]]):
        """Adds batch to awaiting results."""
        for serials, evaluations in batch.items():
            for serial in serials:
                if serial not in self.awaiting_results:
                    self.awaiting_results[serial] = set()

                self.awaiting_results[serial] |= set(evaluation.id for evaluation in evaluations)

    def getBatches(self) -> Generator[dict[set[str], list[Evaluation]]]:
        """Produces batches for client to consume."""
        for batch in self.bundle:
            with self.result_cv:
                if not self._readyForBatch():
                    self.result_cv.wait_for(self._readyForBatch)

                self._addBatch(batch)
                yield batch

    def _readyForBatch(self) -> bool:
        """Whether the next batch should be made available for consumption."""

class QuickBatchFactory(AbstractBatchFactory):
    """
    Sends all batches to workers without any delay.
    """
    def _readyForBatch(self):
        return True

class PatientBatchFactory(AbstractBatchFactory):
    """
    Waits until all workers have finished processing a batch
    before sending a new one.
    """
    def _readyForBatch(self):
        return not any(self.awaiting_results.values())

class BalancedBatchFactory(AbstractBatchFactory):
    """
    Starts by sending an initial amount of batches, then
    waits until a threshold of results have been received
    before sending more batches.
    """
    def __init__(self, evaluations, target_batches=4, batch_size=5):
        super().__init__(evaluations, batch_size=batch_size)
        self.target_batches = target_batches

    def _readyForBatch(self):
        if not any(self.awaiting_results.values()):
            return True

        highest_queued = max(map(len, self.awaiting_results.values()))
        batches = math.floor(highest_queued / self.bundle.batch_size)
        return bool(self.target_batches - batches)


class ResultHandler(AbstractEventHandler):
    """Receives and processes results of circuit evaluations."""
    def __init__(self, event_server, client: BatchClient):
        super().__init__(event_server)
        self.client = client

    @register("results", "batch_id", "serial", "results")
    def results(self, batch_id: str, serial: str, results: Dict[str, int]):
        factory = self.client.batch_factories.get(batch_id)
        if not factory:
            return

        for uid, pulses in results:
            factory.processResult(serial, uid, pulses)

class BatchClient(BaseClient):
    def __init__(self, url, client_name, logger):
        super().__init__(url, client_name, logger)

        self.batch_factories: dict[str, AbstractBatchFactory] = {}
        self.addEventHandler(ResultHandler(self.server, self))

    def _evaluateBatch(self, evaluations: list[Evaluation], batch_id: str):
        out = []
        for evaluation in evaluations:
            out.append(self.requestBatchWorker(list(evaluation.serials), "evaluate", evaluation.toJson(batch_id)))

        return out

    def _evaluateFactory(self, factory: AbstractBatchFactory) -> Generator[tuple[str, Evaluation, Any]]:
        """Returns serial, source evaluation, result"""
        self.batch_factories[factory.bundle.id] = factory

        def evaluate_batches():
            for evaluations in factory.getBatches():
                for serial_group in evaluations.values():
                    self._evaluateBatch(serial_group, factory.bundle.id)

        threading.Thread(target=evaluate_batches, name="batch-sender").start()

        for result in factory.getResults():
            yield result

        del self.batch_factories[factory.bundle.id]

    #TODO switch this to just evaluate, requires bitstreamevo changes
    def evaluateEvaluations(self, evaluations: List[Evaluation], batch_size=5, target_batches=2) -> Generator[tuple[str, Evaluation, Any]]:
        return self._evaluateFactory(BalancedBatchFactory(evaluations, batch_size=batch_size, target_batches=target_batches))

