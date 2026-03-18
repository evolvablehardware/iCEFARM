from __future__ import annotations
import uuid
import threading
import math
from collections import Counter
from collections.abc import Generator
from abc import ABC, abstractmethod
from typing import Any, List, Dict
import time

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

class AbstractBatchFactory(ABC):
    # TODO at some point this should support adding evaluations to an existing factory,
    # this will give a slight speedup as partial generations can be sent while using icepack
    """
    Produces batches for client consumption.
    """
    # this could be easily replaced with a bundle, not needed and complicated for now
    def __init__(self, evaluations: list[Evaluation], batch_size: int, client: BaseClient, result_timeout=20, unreserve_on_timeout=True):
        super().__init__()
        self.bundle = EvaluationBundle(evaluations, batch_size=batch_size)
        self.results: list[tuple[Evaluation, dict]] = []
        self.result_cv = threading.Condition()

        self.awaiting_results: dict[str, set] = {}
        self.serial_last_result: dict[str, float] = {}

        self.result_timeout = result_timeout
        self.unreserve_on_timeout = unreserve_on_timeout
        self.client = client
        self.broken_serials = set()

        self.thread = None
        self.stop_thread = False
        self.startWatchdog()

    def startWatchdog(self):
        def watch():
            while not self.stop_thread:
                time.sleep(self.result_timeout)

                with self.result_cv:
                    awaiting_serials = [serial for serial in self.awaiting_results if self.awaiting_results.get(serial)]
                    expired_serials = [serial for serial in awaiting_serials if self.serial_last_result[serial] + self.result_timeout < time.time()]
                    newly_expired_serials = [serial for serial in expired_serials if serial not in self.broken_serials]

                    failed_evaluations = []

                    for serial in newly_expired_serials:
                        self.client.logger.warning(f"timeout detected on device {serial} during evaluation, rebooting")
                        if not self.client.reboot(serial):
                            self.client.logger.error(f"device {serial} reboot failed, ending reservation")
                            self.client.end([serial])
                            self.broken_serials.add(serial)

                            for evaluation_id in self.awaiting_results[serial]:
                                failed_evaluations.append((serial, evaluation_id, EvaluationFailed))
                        else:
                            self.client.logger.info(f"device {serial} reboot succeed")

                for evaluation in failed_evaluations:
                    self.processResult(*evaluation)

        self.thread = threading.Thread(target=watch, name="batchfactory-watchdog", daemon=True)
        self.thread.start()

    def processResult(self, serial: str, evaluation_id: str, result: Any):
        with self.result_cv:
            if serial not in self.awaiting_results:
                return

            if evaluation_id not in self.awaiting_results[serial]:
                return

            self.awaiting_results[serial] -= {evaluation_id}
            self.serial_last_result[serial] = time.time()

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
                    self.exit()
                    return

    def _addBatch(self, batch: dict[set[str], list[Evaluation]]):
        """Adds batch to awaiting results and adds any serials included to serial_last_result."""
        bad_results = []
        for serials, evaluations in batch.items():
            for serial in serials:
                with self.result_cv:
                    if serial not in self.serial_last_result:
                        self.serial_last_result[serial] = time.time()

                if serial not in self.awaiting_results:
                    self.awaiting_results[serial] = set()

                self.awaiting_results[serial] |= set(evaluation.id for evaluation in evaluations)

                if serial in self.broken_serials:
                    bad_results.extend((serial, evaluation.id, EvaluationFailed) for evaluation in evaluations)

        for result in bad_results:
            self.processResult(*result)


    def getBatches(self) -> Generator[dict[set[str], list[Evaluation]]]:
        """Produces batches for client to consume."""
        for batch in self.bundle:
            with self.result_cv:
                if not self._readyForBatch():
                    self.result_cv.wait_for(self._readyForBatch)

                self._addBatch(batch)
                yield batch

    def exit(self):
        self.stop_thread = True

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
    def __init__(self, evaluations, client, target_batches=4, batch_size=5):
        super().__init__(evaluations, batch_size, client)
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

    # TODO figure out better design for broken devices during batches
    # Need to improve EvaluationBundle first
    def _evaluateBatch(self, evaluations: list[Evaluation], batch_id: str, bad_serials: set[str]):
        out = []
        for evaluation in evaluations:
            out.append(self.requestBatchWorker(list(evaluation.serials - bad_serials), "evaluate", evaluation.toJson(batch_id)))

        return out

    def _evaluateFactory(self, factory: AbstractBatchFactory) -> Generator[tuple[str, Evaluation, Any]]:
        """Returns serial, source evaluation, result"""
        self.batch_factories[factory.bundle.id] = factory

        def evaluate_batches():
            for evaluations in factory.getBatches():
                for serial_group in evaluations.values():
                    # TODO improve EvaluationBundle so bad serials are not generated in the first place?
                    # I don't like that method really because it means that evaluations with multiple devices will be
                    # run for none of them

                    # I think the best option is to generate the serials in the batchfactory alongside the evaluations and ignore the listed
                    # serials in the evaluation object itself
                    self._evaluateBatch(serial_group, factory.bundle.id, factory.broken_serials)

        threading.Thread(target=evaluate_batches, name="batch-sender").start()

        for result in factory.getResults():
            yield result

        del self.batch_factories[factory.bundle.id]

    #TODO switch this to just evaluate, requires bitstreamevo changes
    def evaluateEvaluations(self, evaluations: List[Evaluation], batch_size=5, target_batches=2) -> Generator[tuple[str, Evaluation, Any]]:
        return self._evaluateFactory(BalancedBatchFactory(evaluations, self, batch_size=batch_size, target_batches=target_batches))

