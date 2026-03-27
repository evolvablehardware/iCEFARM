from __future__ import annotations
import uuid
import threading
import math
from collections import Counter
from collections.abc import Generator
from abc import ABC, abstractmethod
from typing import Any, List, Dict
import time
from dataclasses import dataclass
import itertools

from icefarm.utils import MappedQueues, Queue
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

class EvaluationFailed: ...

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

@dataclass
class Result:
    serial: str
    evaluation: Evaluation
    value: Any | EvaluationFailed

class ResultTracker:
    """Tracks evaluations to know when all results have been received. Also keeps track of
    how long devices have gone without sending back results."""
    def __init__(self, bundle: EvaluationBundle):
        self.bundle = bundle

        self.lock = threading.RLock()
        # serial -> Evaluations
        self.awaiting_results: dict[str, set[Evaluation]] = {}
        self.serial_last_result: dict[str, float] = {}
        self.results: Queue[Result] = Queue()

        self.broken_serials: set[str] = set()

    def getSerialTimeouts(self, duration: float) -> set[str]:
        """Returns serials that are expecting results but have not
        received any within the duration."""
        with self.lock:
            return set(serial for serial, last_result in self.serial_last_result.items() if last_result + duration < time.time())

    def markBrokenSerial(self, serial: str):
        """Marks a serial as broken. Whenever an evaluation for a broken device that is tracked,
        and for those already being tracked, a Result is created with an EvaluationFailed value
        instead of waiting for a value."""
        with self.lock:
            self.broken_serials.add(serial)

            for evaluation in list(self.awaiting_results.get(serial, [])):
                self.processResult(Result(serial, evaluation, EvaluationFailed))

    def trackEvaluation(self, serial: str, evaluation: Evaluation):
        """Starts tracking an evaluation. Result processing does not stop until all tracked
        evaluations are processed or invalidated."""
        with self.lock:
            if serial not in self.awaiting_results:
                self.serial_last_result[serial] = time.time()

            if serial not in self.awaiting_results:
                self.awaiting_results[serial] = set()

            self.awaiting_results[serial].add(evaluation)

            if serial in self.broken_serials:
                result = Result(serial, evaluation, EvaluationFailed)
                self.processResult(result)
                print("\n\nADDED FAILED RESULTS\n\n")

    def processResult(self, result: Result):
        """Updates tracked evaluations to mark this one as completed, forwards the result to
        caller of getResults."""
        with self.lock:
            if result.evaluation not in self.awaiting_results.get(result.serial, []):
                return

            self.awaiting_results[result.serial].discard(result.evaluation)
            self.serial_last_result[result.serial] = time.time()
            self.results.put(result)

            # TODO would be nice to get rid of bundle
            # dependence but I think having a to set a flag for empty
            # is less straightforward
            if self.bundle.empty and not any(self.awaiting_results.values()):
                self.results.put(None)

    def getResults(self) -> Generator[Result]:
        """Returns results as they are processed."""
        while res := self.results.pop():
            yield res

class AbstractBatchFactory(ABC):
    # TODO at some point this should support adding evaluations to an existing factory,
    # this will give a slight speedup as partial generations can be sent while using icepack
    """
    Produces batches for client consumption.
    """
    def __init__(self, bundle: EvaluationBundle, client: BaseClient, result_timeout=None, unreserve_on_timeout=True):
        super().__init__()
        self.bundle = bundle
        self.tracker = ResultTracker(bundle)
        self.result_cv = threading.Condition()

        self.result_timeout = result_timeout
        self.unreserve_on_timeout = unreserve_on_timeout
        self.client = client

        self.thread = None
        self.stop = threading.Event()
        self.startWatchdog()

    def startWatchdog(self):
        def watch():
            while not self.stop.wait(self.result_timeout):
                failed_serials = list(self.tracker.getSerialTimeouts(self.result_timeout))

                if self.unreserve_on_timeout:
                    self.client.end(failed_serials)

                for serial in failed_serials:
                    self.tracker.markBrokenSerial(serial)

        self.thread = threading.Thread(target=watch, name="batchfactory-watchdog", daemon=True)
        self.thread.start()

    def processResult(self, serial: str, evaluation_id: str, value: Any):
        with self.result_cv:
            evaluation = self.bundle.evaluation_lookup[evaluation_id]
            result = Result(serial, evaluation, value)

            self.tracker.processResult(result)
            self.result_cv.notify_all()

    def getResults(self) -> Generator[Result]:
        """Produces results as they received by processResult."""
        yield from self.tracker.getResults()

    def getBatches(self) -> Generator[dict[set[str], list[Evaluation]]]:
        """Produces batches for client to consume."""
        # TODO kinda suboptimal but should not matter
        with self.result_cv:
            for batch in self.bundle:
                if not self._readyForBatch():
                    self.result_cv.wait_for(self._readyForBatch)

                for serials, evaluations in batch.items():
                    pairs = itertools.product(serials, evaluations)
                    for serial, evaluation in pairs:
                        self.tracker.trackEvaluation(serial, evaluation)

                # remove broken serials from evaluations
                actual_batch: dict[set[str], list[Evaluation]] = {}
                for serials, evaluations in batch.items():
                    working_serials = serials.difference(self.tracker.broken_serials)
                    current_evaluations = actual_batch.get(working_serials, [])

                    current_evaluations.extend(evaluations)
                    actual_batch[working_serials] = current_evaluations

                yield actual_batch

    def exit(self):
        self.stop.set()

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
        return not any(self.tracker.awaiting_results.values())

class BalancedBatchFactory(AbstractBatchFactory):
    """
    Starts by sending an initial amount of batches, then
    waits until a threshold of results have been received
    before sending more batches.
    """
    def __init__(self, bundle, client, target_batches=4, result_timeout=None, unreserve_on_timeout=True):
        super().__init__(bundle, client, result_timeout, unreserve_on_timeout)
        self.target_batches = target_batches

    def _readyForBatch(self):
        if not any(self.tracker.awaiting_results.values()):
            return True

        highest_queued = max(map(len, self.tracker.awaiting_results.values()))
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

    def _evaluateFactory(self, factory: AbstractBatchFactory) -> Generator[Result]:
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
    def evaluateEvaluations(self, evaluations: List[Evaluation], result_timeout=30, batch_size=5, target_batches=2) -> Generator[Result]:
        bundle = EvaluationBundle(evaluations, batch_size=batch_size)
        return self._evaluateFactory(BalancedBatchFactory(bundle, self, target_batches=target_batches, result_timeout=result_timeout))

