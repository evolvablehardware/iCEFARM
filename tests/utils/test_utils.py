from icefarm.utils import MappedQueues, json_to_args, batch

def test_json_to_args():
    json = {
        "a": 1,
        "b": 2,
        "c": 3
    }

    args = ("b", "c", "a")
    assert json_to_args(json, args) == [2, 3, 1]
    assert json_to_args(json, ("d")) == False

def test_batch():
    items = list(range(10))
    assert batch(items, 1)[0] == list(range(10))

    for batch_size in range(1, 10):
        items = set()
        for b in batch(list(range(100)), batch_size):
            items.update(b)

        assert items == set(range(100))

def test_mapped_queues():
    queue = MappedQueues()

    for k in [1, 2, 3]:
        assert queue[k] == []
        assert k not in queue

    for _ in queue:
        raise Exception("Queue should be empty")

    for _ in queue.keys():
        raise Exception("Queue should be empty")

    for _ in queue.values():
        raise Exception("Queue should be empty")

    if queue:
        raise Exception("Queue should be empty")

    for i in range(10):
        queue.append("k", i)

    assert queue["k"] == list(range(10))

    assert queue.pop("k", 1) == [0]
    assert queue.pop("k", 1) == [1]
    assert queue.pop("k", 2) == [2, 3]
    assert queue.pop("k", 1000) == [4, 5, 6, 7, 8, 9]

    for _ in queue:
        raise Exception("Queue should be empty")
