from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from icefarm.client.lib import EventServer, Event

REGISTERED_METHODS = {}

# TODO replace json with dataclasses

class JsonMethodCall:
    """Allows attribute to be called with json arguments. Argument order must
    match that of the function.
    ```python
    class Example:
        def method(self, a, b)
            return (a, b)

    call_method = JsonMethodCall("method", ["arg_a", "arg_b"])
    example = Example()
    assert call_method(example, {"arg_a": 1, "arg_b": 2}) == (1, 2)
    ```

    """
    def __init__(self, name: str, args: list[str]):
        self.name = name
        self.parms = args

    def __call__(self, obj, data):
        args = list(map(data.get, self.parms))

        if None in args:
            return False

        if not hasattr(obj, self.name):
            return False

        fn = getattr(obj, self.name)

        return fn(*args)

def register(channel, *args):
    """Registers a EventHandler method with the worker/control -> client
    communication system. Any message received under the channel will be
    have the messages json arguments keyed into method arguments based
    on the argument order.
    ```python
    class EventHandler(AbstractEventHandler):
        @register("print_channel", "message", "name")
        def print(self, message, name)
            print(f"Received {message} from {name}!")
    ```
    Receiving the following message from a worker or the control server wil result in
    "Received Hello! from worker1! being printed:
    ```
    "contents": {
        "event": "print_channel",
        "message": "Hello!",
        "name": "worker1"
    }

    ```
    """
    class Register:
        def __init__(self, fn):
            self.fn = fn

        def __set_name__(self, owner, name):
            if owner not in REGISTERED_METHODS:
                REGISTERED_METHODS[owner] = {}

            REGISTERED_METHODS[owner][channel] = JsonMethodCall(name, args)

            setattr(owner, name, self.fn)

    return Register

class AbstractEventHandler:
    def __init__(self, event_server: EventServer):
        self.event_server = event_server

    def exit(self):
        """Called on EventServer shutdown."""

    def sendEvent(self, event: Event):
        self.event_server.sendEvent(event)

    # TODO this was originally designed so that when registered methods
    # are overloaded it acts like they are themselves registered. This
    # allows template eventhandlers to be made and overloaded without having
    # to know how the communication system works. I believe that this fails
    # under some conditions though, don't remember which.
    def handleEvent(self, event: Event):
        """Dispatches event to registered methods."""
        search = [type(self)]
        attr = None

        while search:
            type_ = search.pop(0)
            methods = REGISTERED_METHODS.get(type_)

            if not methods:
                continue

            attr = methods.get(event.event)

            if attr:
                break

            for cls in reversed(type_.__bases__):
                search.insert(0, cls)

        if not attr:
            return False

        return attr(self, event.contents)
