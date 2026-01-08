import uuid
import threading
import math
from collections import Counter
from collections.abc import Generator

from usbipice.utils import MappedQueues

class Evaluation:
    """
    Circuit evaluation to be sent to the worker. Note that providing
    multiple serials to one Evaluation will result in faster evaluations than
    providing multiple Evaluations of the same bitstream.
    """
    def __init__(self, serials: set[str], request: dict):
        self.serials = serials
        self.request = request
        self.id = str(uuid.uuid4())

    def __eq__(self, other):
        return self.id  == other.id

    def __hash__(self):
        return hash(self.id)

class EvaluationBundle:
    """
    Bundles Evaluations into efficient batches for client consumption.
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
        serial_amounts = Counter()
        batch = {}

        search_order = sorted(self.queue.keys(), len)
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

class AbstractBatchFactory:
    """
    Produces batches for client to consume and processes
    results
    """
    def __init__(self, bundle: EvaluationBundle):
        self.bundle = bundle
        self.results: list[tuple[Evaluation, dict]] = []
        self.result_cv = threading.Condition()

        self.awaiting_results: dict[str, set] = {}

    def processResult(self, serial, evaluation_id, result):
        with self.result_cv:
            if serial not in self.awaiting_results:
                return

            if evaluation_id not in self.awaiting_results[serial]:
                return

            self.awaiting_results[serial][evaluation_id] -= evaluation_id
            self.results.append((evaluation_id, result))
            self.result_cv.notify_all()

    def getResults(self) -> Generator[tuple[Evaluation, dict]]:
        """Produces results as they are processed."""
        while True:
            with self.result_cv:
                if not self.results:
                    self.result_cv.wait_for(lambda : self.results)

                for evaluation_id, result in self.results:
                    evaluation = self.bundle.evaluation_lookup.get(evaluation_id)
                    yield evaluation, result

                self.results = []

                if self.bundle.empty and not self.awaiting_results:
                    return

    def _addBatch(self, batch: dict[set[str], list[Evaluation]]):
        """Adds batch to awaiting results."""
        for serials, evaluations in batch.items():
            for serial in serials:
                if serial not in self.awaiting_results:
                    self.awaiting_results[serial] = set()

                self.awaiting_results[serial] += set(evaluation.id for evaluation in evaluations)

    def getBatches(self) -> Generator[dict[set[str], list[Evaluation]]]:
        """Produces batches for client to consume."""
        for batch in self.bundle:
            with self.result_cv:
                if self.awaiting_results:
                    self.result_cv.wait_for(self._readyForBatch)
                    self._addBatch(batch)
                    yield batch

    def _readyForBatch(self):
        pass

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
        return not self.awaiting_results

class BalancedBatchFactory(AbstractBatchFactory):
    """
    Starts by sending an initial amount of batches, then
    waits until a threshold of results have been received
    before sending more batches.
    """
    def __init__(self, bundle, target_batches=2):
        super().__init__(bundle)
        self.target_batches = target_batches

    def _readyForBatch(self):
        highest_queued = max(map(len, self.awaiting_results.values()))
        batches = math.ceil(highest_queued / self.bundle.batch_size)
        return bool(self.target_batches - batches)
