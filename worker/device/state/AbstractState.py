from __future__ import annotations
import threading
from logging import Logger
from abc import ABC

from worker.WorkerDatabase import WorkerDatabase
from utils.NotificationSender import NotificationSender
from utils.dev import *

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from worker.device import Device

class EventMethod:
    def __init__(self, method, parms):
        self.method = method
        self.parms = parms

    def __call__(self, device, data):
        args = list(map(data.get, self.parms))

        if None in args:
            return False

        return self.method(device, *args)

class AbstractState(ABC):
    methods = {}

    def __init__(self, state: Device):
        super().__init__()
        self.state = state
        self.switching = False
        self.switching_lock = threading.Lock()

        name = type(self).__name__
        self.getLogger().debug(f"state is now {name}")

    def handleAdd(self, dev: pyudev.Device):
        """Called on ADD device event."""

    def handleRemove(self, dev: pyudev.Device):
        """Called on REMOVE device event."""

    def handleExit(self):
        """Cleanup."""

    def getState(self) -> Device:
        return self.state

    def getSerial(self) -> str:
        return self.getState().getSerial()

    def getLogger(self) -> Logger:
        return self.getState().getLogger()

    def getDatabase(self) -> WorkerDatabase:
        return self.getState().getDatabase()

    def getNotif(self) -> NotificationSender:
        return self.getState().getNotif()

    def switch(self, state_factory):
        # prevents multiple switches
        # from happening
        with self.switching_lock:
            if self.switching:
                return

            self.switching = True

            return self.getState().switch(state_factory)

    def isSwitching(self) -> bool:
        return self.switching

    def getSwitchingLock(self) -> threading.Lock:
        return self.switching_lock

    @classmethod
    def register(cls, event, *args):
        """Adds a method to the methods dictionary, which allows it to be called 
        using the handleEvent function with event=event. These arguments specify which json 
        key should be used to get the value of that positional argument when handleEvent is called.

        Ex. 
        >>> class ExampleDevice:  
                @AbstractState.register("add", "value 1", "value 2")  
                def addNumbers(self, a, b):  
                    return a + b  
        
        >>> ExampleDevice().handleEvent("add", {  
            "value 1": 1,  
            "value 2": 2  
        })  
        3
        """
        class Reg:
            def __init__(self, fn):
                self.fn = fn

            # hacky way to get reference to class
            # type within its own initiation
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
            return False

        method = methods.get(event)

        if method:
            return method(self, json)

        return False
