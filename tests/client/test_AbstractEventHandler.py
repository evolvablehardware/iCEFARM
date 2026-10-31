from icefarm.utils import BaseEvent
from icefarm.client.lib.AbstractEventHandler import AbstractEventHandler, register
from icefarm.utils import DeviceFailure, DeviceInitialized

class _TestEvent(BaseEvent, register_args=("value",)):
    def __init__(self, value):
        self.value = value

def test_abstract_event_handler():
    class EventHandler(AbstractEventHandler):
        def __init__(self):
            super().__init__(None)
            # invoked methods don't return, side effect
            self.fn1_value = None
            self.fn2_value = None

        @register(_TestEvent)
        def fn1(self, event):
            self.fn1_value = event.value

        @register(DeviceFailure)
        def fn2(self, event):
            self.fn2_value = event.serial

    handler = EventHandler()

    handler.handleEvent(_TestEvent(1))
    assert handler.fn1_value == 1

    handler.handleEvent(DeviceFailure("serial"))
    assert handler.fn2_value == "serial"

def test_abstract_event_handler_unregistered():
    class EventHandler(AbstractEventHandler):
        @register(DeviceFailure)
        def handle(self, event):
            raise Exception("should not be called")

    assert EventHandler(None).handleEvent(DeviceInitialized("serial")) is False
