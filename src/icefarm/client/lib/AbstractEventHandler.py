from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from icefarm.client.lib import EventServer, Event

REGISTERED_METHODS = {}

class JsonMethodCall:
    def __init__(self, name, args):
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

def register(key, *args):
    class Register:
        def __init__(self, fn):
            self.fn = fn

        def __set_name__(self, owner, name):
            if owner not in REGISTERED_METHODS:
                REGISTERED_METHODS[owner] = {}

            REGISTERED_METHODS[owner][key] = JsonMethodCall(name, args)

            setattr(owner, name, self.fn)

    return Register

class AbstractEventHandler:
    def __init__(self, event_server: EventServer):
        self.event_server = event_server

    def exit(self):
        """Called on EventServer shutdown."""

    def sendEvent(self, event: Event):
        self.event_server.sendEvent(event)

    def handleEvent(self, event):
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
