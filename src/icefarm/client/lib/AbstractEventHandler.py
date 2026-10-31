from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from icefarm.client.lib import EventServer
    from icefarm.utils import BaseEvent

# owner class -> event class -> method name
REGISTERED_METHODS: dict[type, dict[type[BaseEvent], str]] = {}

def register(event_cls: type[BaseEvent]):
    """Registers a EventHandler method with the worker/control -> client
    communication system. The method is called with the event object whenever
    an event of type event_cls (or a subclass of it) is received.
    ```python
    class EventHandler(AbstractEventHandler):
        @register(DeviceFailure)
        def handleFailure(self, event: DeviceFailure):
            print(f"Device {event.serial} failed!")
    ```
    """
    class Register:
        def __init__(self, fn):
            self.fn = fn

        def __set_name__(self, owner, name):
            if owner not in REGISTERED_METHODS:
                REGISTERED_METHODS[owner] = {}

            REGISTERED_METHODS[owner][event_cls] = name

            setattr(owner, name, self.fn)

    return Register

class AbstractEventHandler:
    def __init__(self, event_server: EventServer):
        self.event_server = event_server

    def exit(self):
        """Called on EventServer shutdown."""

    def sendEvent(self, event: BaseEvent):
        self.event_server.handleEvent(event)

    # TODO this was originally designed so that when registered methods
    # are overloaded it acts like they are themselves registered. This
    # allows template eventhandlers to be made and overloaded without having
    # to know how the communication system works. I believe that this fails
    # under some conditions though, don't remember which.
    def handleEvent(self, event: BaseEvent):
        """Dispatches event to registered methods."""
        event_types = type(event).__mro__

        search = [type(self)]
        while search:
            type_ = search.pop(0)
            methods = REGISTERED_METHODS.get(type_)

            if methods:
                for event_type in event_types:
                    name = methods.get(event_type)

                    if name:
                        return getattr(self, name)(event)

            for cls in reversed(type_.__bases__):
                search.insert(0, cls)

        return False
