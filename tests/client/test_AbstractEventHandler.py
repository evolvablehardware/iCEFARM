from icefarm.client.lib.AbstractEventHandler import JsonMethodCall, AbstractEventHandler, register
from icefarm.client.lib import Event


def test_json_method_call():
    class Test():
        def fn1(self):
            return True

        def fn2(self, a, b, c):
            return a, b, c

    fn1_call = JsonMethodCall("fn1", [])
    fn2_call = JsonMethodCall("fn2", ["a", "b", "c"])

    test = Test()
    assert fn1_call(test, {})
    assert fn1_call(test, {"asdf": 1})
    assert fn2_call(test, {"a":1, "b":2, "c":3}) == (1, 2, 3)


def test_abstract_event_handler():
    class EventHandler(AbstractEventHandler):
        def __init__(self):
            super().__init__(None)
            # invoked methods don't return, side effect
            self.fn1_value = None
            self.fn2_value = None

        @register("fn1_call")
        def fn1(self):
            self.fn1_value = True

        @register("fn2_call", "a", "b")
        def fn2(self, a, b):
            self.fn2_value = (a, b)

    handler = EventHandler()

    handler.handleEvent(Event(None, "fn1_call", {}))
    assert handler.fn1_value

    handler.handleEvent(Event(None, "fn2_call", {"a":1, "b":2}))
    assert handler.fn2_value == (1, 2)
