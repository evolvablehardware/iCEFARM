from icefarm.client.lib.BatchClient import Evaluation, EvaluationFailed, EvaluationBundle, Result, ResultTracker

from collections import defaultdict
import itertools
import time


class TestEvaluation(Evaluation):
    def _toJson(self):
        pass

def sanity_evaluation_bundle(evals: set[Evaluation], batch_size=10):
    """Sanity test for evaluation bundle, modifies evals in place. Ensures that batches can be properly consumed
    but does ensure they are packaged for optimal network transfer speed."""
    bundle = EvaluationBundle(evals, batch_size=batch_size)
    serials = {ev.serials for ev in evals}

    # amount of serials in each batch should be nonincreasing
    last_serials_amount = len(serials)
    # amount of evaluations per serial should be nonincreasing
    last_evals_amount = {serial: batch_size for serial in serials}

    for batch in bundle:
        if len(batch) > last_serials_amount:
            raise Exception("Amount of serials evaluated increased")

        last_serials_amount = len(batch)

        for serial, serial_evals in batch.items():
            if len(serial_evals) > last_evals_amount[serial]:
                raise Exception(f"Amount of evaluations for {serial:} increased")

            last_evals_amount[serial] = len(serial_evals)
            for serial_eval in serial_evals:
                evals.remove(serial_eval)

    if len(evals):
        raise Exception(f"Some evaluations did not get batched: {len(evals)}")

def get_evaluations(serials=list(range(5)), amount=30):
    """Returns amount evaluation for each combination serials."""
    evals = set()

    # all combinations of serials
    for batched_serials in itertools.chain(itertools.combinations(serials, i) for i in range(1, len(serials)+1)):
        # serials is consumable here
        batched_serials = set(batched_serials)
        for _ in range(amount):
            evals.add(TestEvaluation(batched_serials))

    return evals

def test_evaluation_bundle():
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

# TODO test with consumer thread








