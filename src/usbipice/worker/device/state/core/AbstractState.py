from __future__ import annotations
import threading
from logging import Logger, LoggerAdapter

from usbipice.utils import typecheck
from usbipice.utils.dev import *
from usbipice.worker.device import Device

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from usbipice.worker import WorkerDatabase, Config, DeviceEventSender

class EventMethod:
    def __init__(self, method, parms):
        self.method = method
        self.parms = parms

    def __call__(self, device, data):
        args = list(map(data.get, self.parms))

        if None in args:
            return

        if not typecheck(self.method, (device, *args)):
            return

        return self.method(device, *args)

class StateLogger(LoggerAdapter):
    def __init__(self, logger: Logger, state: str, extra = None):
        self.state = state
        super().__init__(logger, extra={})

    def process(self, msg, kwargs):
        return f"[{self.state}] {msg}", kwargs

class AbstractState:
    methods = {}

    def __init__(self, device: Device):
        """NOTE: switch CANNOT be called inside __init__(). This will result
        in the lock for Device being a acquired a second time. If this behavior
        is needed, use start() instead."""
        self.device = device

        name = type(self).__name__
        self.logger = StateLogger(self.getDevice().getLogger(), name)

        self.switching = False
        self.switching_lock = threading.RLock()

        self.getLogger().debug(f"state is now {name}")

    def start(self):
        """Called after the AbstractState is initialized, for
        actions that may result in a switch call. Note that handleExit
        may be called during this step."""

    def handleAdd(self, dev: dict):
        """Called on ADD device event."""

    def handleRemove(self, dev: dict):
        """Called on REMOVE device event."""

    def handleExit(self):
        """Cleanup"""

    def getDevice(self) -> Device:
        return self.device

    def getSerial(self) -> str:
        return self.getDevice().getSerial()

    def getLogger(self) -> Logger:
        return self.logger

    def getDatabase(self) -> WorkerDatabase:
        return self.getDevice().getDatabase()

    def getEventSender(self) -> DeviceEventSender:
        return self.getDevice().getEventSender()

    def getConfig(self) -> Config:
        return self.getDevice().getConfig()

    def switch(self, state_factory):
        """Switches the Device's state to a new one. This happens by first calling
        exit on the existing state. After the existing state has exited, the
        state factory is called and the result is set as the state. Subsequent calls
        to switch from the original state object are ignored."""
        with self.switching_lock:
            if self.switching:
                return

            self.switching = True

        return self.getDevice().switch(state_factory)

    def getSwitchLock(self):
        return self.switching_lock

    def isSwitching(self):
        """Whether the Device is currently switching states"""
        with self.switching_lock:
            return self.switching

    @classmethod
    def register(cls, event, *args):
        # TODO
        # update this for sockets
        # test typechecking with sockets
        """Adds a method to the methods dictionary, which allows it to be called
        using the handleEvent function with event=event. These arguments specify which json
        key should be used to get the value of that positional argument when handleEvent is called.
        The values passed in from the client are typechecked. Currently, only type and list[type]
        are supported. Files should be sent as cp437 encoded bytes. If the file is needed later, it
        should be saved under self.getDevice().getMediaPath(). Parameters without types are treated as Any.

        Ex.
        >>> class ExampleDevice:
                @AbstractState.register("add", "value 1", "value 2")
                def addNumbers(self, a: int, b: int):
                    self.getLogger().info(a + b)
        >>> client.requestWorker("serial", {
                "serial": "ABCDEF",
                "value 1": 1,
                "value 2": 2
        [ABCDEF] 3
        """
        class Reg:
            def __init__(self, fn):
                self.fn = fn

            def __set_name__(self, owner, name):
                if owner not in cls.methods:
                    cls.methods[owner] = {}

                if name in cls.methods[owner]:
                    raise Exception(f"{event} already registered")

                cls.methods[owner][event] = EventMethod(self.fn, args)
                setattr(owner, name, self.fn)

        return Reg

    def handleRequest(self, event, json):
        """Calls method event from the methods dictionary, using the arguments it was registered with
        as keys for the json."""
        methods = AbstractState.methods.get(type(self))

        if not methods:
            return

        method = methods.get(event)

        if method:
            return method(self, json)

        return
