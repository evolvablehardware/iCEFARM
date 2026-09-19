from icefarm.client.lib.BatchClient import *

from collections import defaultdict
import itertools
import time
import threading


class TestEvaluation(Evaluation):
    def _toJson(self):
        pass

def ensure_bundle_serials_nonincreasing(evals: set[Evaluation], batch_size=10):
    bundle = EvaluationBundle(evals, batch_size=batch_size)
    serials = set(itertools.chain.from_iterable(ev.serials for ev in evals))
    last_serials_amount = len(serials)

    for batch in bundle:
        used_serials = set(itertools.chain.from_iterable(batch))
        if len(used_serials) > last_serials_amount:
            raise Exception("Amount of serials evaluated increased")

    last_serials_amount = len(used_serials)

def ensure_bundle_evaluations_nonincreasing(evals: set[Evaluation], batch_size=10):
    bundle = EvaluationBundle(evals, batch_size=batch_size)
    all_serials = set(itertools.chain.from_iterable(ev.serials for ev in evals))
    last_evals_amount = {serial: batch_size for serial in all_serials}

    for batch in bundle:
        amounts = Counter()

        for serials, evaluations in batch.items():
            for serial in serials:
                amounts[serial] += len(evaluations)

        for serial in all_serials:
            assert last_evals_amount[serial] >= amounts[serial]
            last_evals_amount[serial] = amounts[serial]

def sanity_evaluation_bundle(evals: set[Evaluation], batch_size=10):
    """Sanity test for evaluation bundle, modifies evals in place. Ensures that batches can be properly consumed
    but does ensure they are packaged for optimal network transfer speed."""
    evaluation_lookup = {evaluation: set(evaluation.serials) for evaluation in evals}
    bundle = EvaluationBundle(evals, batch_size=batch_size)

    for batch in bundle:
        for serials, evaluations in batch.items():
            for serial in serials:
                for evaluation in evaluations:
                    evaluation_lookup[evaluation].remove(serial)

    for remaining in evaluation_lookup.values():
        if len(remaining):
            raise Exception(f"Some evaluations did not get batched: {len(remaining)}")

def get_evaluations(serials=list(range(5)), amount=30):
    """Returns amount evaluation for each combination serials."""
    evals = set()

    # all combinations of serials
    for batched_serials in itertools.chain.from_iterable(itertools.combinations(serials, i) for i in range(1, len(serials)+1)):
        # serials is consumable here
        batched_serials = set(batched_serials)
        for _ in range(amount):
            evals.add(TestEvaluation(batched_serials))

    return evals

def test_bundle():
    ones = get_evaluations(serials=[1], amount=10)
    bundle = EvaluationBundle(ones, 1)
    assert len(list(bundle)) == 10

    evaluations = []
    for i in range(1, 6):
        evaluations.append(TestEvaluation(set(range(i))))
    bundle = EvaluationBundle(evaluations, 1)

    batches = list(bundle)
    assert len(batches) == 5

    evaluations = []
    for i in range(1, 11):
        for _ in range(3):
            evaluations.append(TestEvaluation(set(range(i))))
    bundle = EvaluationBundle(evaluations, 3)

    batches = list(bundle)
    assert len(batches) == 10

    evaluations = []
    for i in range(1, 15):
        for _ in range(1):
            evaluations.append(TestEvaluation(set(range(i))))
    sanity_evaluation_bundle(set(evaluations), batch_size=1)

def test_evaluation_bundle():
    ensure_bundle_serials_nonincreasing(get_evaluations())
    ensure_bundle_evaluations_nonincreasing(get_evaluations())
    sanity_evaluation_bundle(get_evaluations())

def sanity_result_tracker(evals: set[Evaluation], fail_serials=set()):
    """Sanity test for ResultTracker. Ensures that all processed results
    are actually returned. Does not test with multiple threads. Marks failed_serials
    as failed before processing results and ensures that EvaluationFailed is received."""

    rt = ResultTracker()

    for evaluation in evals:
        for serial in evaluation.serials:
                rt.trackEvaluation(serial, evaluation)

    rt.bundleEmpty()
    for serial in fail_serials:
        rt.markBrokenSerial(serial)

    for evaluation in evals:
        for serial in evaluation.serials:
            result = Result(serial, evaluation, evaluation.id)
            rt.processResult(result)

    # eval -> serial -> results
    results = defaultdict(dict)

    for res in rt.getResults():
        results[res.evaluation][res.serial] = res.value

    for eval in evals:
        for serial in eval.serials:
            res = results[eval].pop(serial)

            if serial in fail_serials:
                assert res is EvaluationFailed
            else:
                assert res == eval.id

    for remaining in results.values():
        assert len(remaining) == 0

def test_sanity_result_tracker():
    sanity_result_tracker(get_evaluations(serials=range(5)), fail_serials={0})

def test_result_tracker_timeouts():
    """Ensures that the tracking of last received result time per serial
    is working."""
    a_evals = [TestEvaluation("a") for _ in range(3)]
    b_evals = [TestEvaluation("b") for _ in range(3)]
    all_evals = a_evals + b_evals
    rt = ResultTracker()

    for eval in all_evals:
        for serial in eval.serials:
            rt.trackEvaluation(serial, eval)

    time.sleep(0.3)
    assert rt.getSerialTimeouts(0.2) == {"a", "b"}

    rt.processResult(Result("a", a_evals.pop(), None))
    assert rt.getSerialTimeouts(0.2) == {"b"}

def result_tracker_threaded(evals: set[Evaluation]):
    """Ensure that results can be consumed directly after they are produced.
    Also ensures that consumer exists when all results are finished."""

    rt = ResultTracker()

    for evaluation in evals:
        for serial in evaluation.serials:
                rt.trackEvaluation(serial, evaluation)

    rt.bundleEmpty()

    ready = threading.Event()
    ready.set()

    done = threading.Event()

    def consume():
        for _ in rt.getResults():
            ready.set()

        done.set()

    threading.Thread(target=consume, daemon=True, name="consumer").start()

    for evaluation in evals:
        for serial in evaluation.serials:
            if done.is_set():
                raise Exception("Consumer exited early")

            if not ready.wait(timeout=1):
                raise Exception("Consumer did not consume result in time")

            ready.clear()

            result = Result(serial, evaluation, evaluation.id)
            rt.processResult(result)


    if not done.wait(timeout=1):
        raise Exception("Consumer did not exit in time")

def test_result_tracker_threaded():
    result_tracker_threaded(get_evaluations())

def batch_factory_get_batches(evals: set[Evaluation]):
    evals_copy = set(evals)
    bundle = EvaluationBundle(evals, 5)
    # client integration only used for timeout watchdog
    factory = PatientBatchFactory(bundle, None)

    for batch in factory.getBatches():
        for serials, evaluations in batch.items():
            for serial, evaluation in itertools.product(serials, evaluations):
                factory.processResult(serial, evaluation.id, evaluation.id)

    results = defaultdict(dict)

    for res in factory.getResults():
        results[res.evaluation][res.serial] = res.value

    for evaluation in evals_copy:
        for serial in evaluation.serials:
            res = results[evaluation].pop(serial)
            assert res == evaluation.id

    for remaining in results.values():
        assert len(remaining) == 0

def test_batch_factory_get_batches():
    batch_factory_get_batches(get_evaluations(serials=[1, 2, 3], amount=1))
    # batch_factory_get_batches(get_evaluations(serials=[1, 2, 3], amount=1))


