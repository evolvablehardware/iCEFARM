from __future__ import annotations
from abc import ABC

from utils.usbip import usbip_attach

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from client.Client import Client

class EventHandler(ABC):
    """Provides methods to handle events produced by an EventServer."""
    def handleExport(self, client: Client, serial: str, bus: str, worker_ip: str, worker_port: str):
        """This is called when the host worker exports a reserved device."""

    def handleDisconnect(self, client: Client, serial: str):
        """This is called when the host worker is no longer exporting the device with usbip.
        This can happen normally, for example, during reboot after a firmware change. However, 
        if it's unexpected something probably went wrong."""

    def handleReservationEnd(self, client: Client, serial: str):
        """This is called when a devices reservation ends. The device will be unbound from the workers side -
        there is no way to retain access to a device after the reservation is over."""

    def handleReservationEndingSoon(self, client: Client, serial: str):
        """This is called when a reservation is ending soon. It is intended to be used to extend
        the reservation time."""

    def handleFailure(self, client: Client, serial: str):
        """This is called when a device failure occurs that is unrecoverable, such as the host worker failing
        a heartbeat check. It is not possible to connect back to the device."""

    def handleTimeout(self, client: Client, serial: str, ip: str, port: str):
        """This is called when the client disconnects from the host bus, but the host is not aware and is still
        exporting the device. The client cannot reconnect to the device since it is still being exported. This is used 
        to instruct the host to rebind the device."""

    def exit(self, client):
        """Called when the EventServer is stopped. Can be used to cleanup any created resources."""

class DefaultEventHandler(EventHandler):
    """Provides usbip basic functionality and serves as an example.
        - attach to devices when they are exported
        - extend reservations when they are ending soon
        - provide logging when devices disconnect, fail, or reservations expire
        - instructs worker to unbind device when timeouts occur (does not provide any means to actually detect timeouts)"""
    def __init__(self, logger):
        self.logger = logger

    def handleExport(self, client: Client, serial: str, bus: str, worker_ip: str, worker_port: str):
        """Tries to attach to a device when it is exported. Prints an error if it fails."""
        if usbip_attach(worker_ip, bus, tcp_port=worker_port):
            self.logger.info(f"bound device {serial} on {worker_ip}:{bus}")
        else:
            self.logger.error(f"failed to bind device {serial} on {worker_ip}:{bus} port {worker_port}")

    def handleDisconnect(self, client: Client, serial: str):
        """Prints an warning."""
        self.logger.warning(f"device {serial} disconnected")

    def handleReservationEndingSoon(self, client: Client, serial: str):
        """Attempts to extend the reservation of the device."""
        if client.extend([serial]):
            self.logger.info(f"refreshed reservation of {serial}")
        else:
            self.logger.error(f"failed to refresh reservation of {serial}")

    def handleReservationEnd(self, client: Client, serial: str):
        """Prints a notification and removes the device from the client"""
        self.logger.info(f"reservation for device {serial} ended")
        client.removeSerial(serial)

    def handleFailure(self, client: Client, serial: str):
        """Prints an error and removes the device from the client"""
        self.logger.error(f"device {serial} failed")
        client.removeSerial(serial)

    def handleTimeout(self, client: Client, serial: str, ip: str, port: str):
        """Prints a warning and instructs the worker to unbind from the device. This will cause the worker
        to rebind the device shortly after and hopefully resolve the issue."""
        self.logger.warning(f"{serial} timed out at {ip}:{port}")
        client.unbind(serial)

    def exit(self, client: Client):
        self.logger.info("Eventhandler exiting!")
