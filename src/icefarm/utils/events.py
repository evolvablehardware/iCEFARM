from __future__ import annotations

from icefarm.utils import BaseEvent

class DeviceInitialized(BaseEvent, register_args=("serial",)):
    """Sent by a worker once a device is ready for client use."""
    def __init__(self, serial: str):
        self.serial = serial

class DeviceReservationEnd(BaseEvent, register_args=("serial",)):
    """Sent when a device reservation ends."""
    def __init__(self, serial: str):
        self.serial = serial

class DeviceFailure(BaseEvent, register_args=("serial",)):
    """Sent when a device fails unexpectedly."""
    def __init__(self, serial: str):
        self.serial = serial

class DeviceReservationEndingSoon(BaseEvent, register_args=("serial",)):
    """Sent when a device reservation is about to expire."""
    def __init__(self, serial: str):
        self.serial = serial

class DevicesAvailable(BaseEvent, register_args=("amount",)):
    """Sent when the amount of devices available for reservation changes."""
    def __init__(self, amount: int):
        self.amount = amount

