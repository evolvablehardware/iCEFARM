from __future__ import annotations
import pyudev

from usbipice.utils.dev import get_busid, get_devs
from usbipice.utils.usbip import usbip_bind, usbip_unbind

from usbipice.worker.device.state.core import AbstractState
from usbipice.worker.device.state.reservable import reservable

import typing
if typing.TYPE_CHECKING:
    from usbipice.worker.device import Device

PORT = "3240"

@reservable("usbip")
class UsbipState(AbstractState):
    """State for connecting to a device over usbip. Reservable as usbip.

        Events:
            - export, called when the device becomes available for connection with usbip
                - busid
                - usbip_port
                - server_ip
            - disconnect, called when the device disconnects from usbip.
            This notification is delayed, and in the event that a device
            disconnects and then reconnects, the export event may be received
            before the disconnect one.
        Interface:
            - unbind, unbinds the device from usbip. This can be used to force reexports when \
            the worker thinks that the client is still connected but has actually disconnected.
    """
    def __init__(self, state):
        super().__init__(state)
        self.busid = None
        self.notif = UsbipEventSender(self)

        # TODO this disconnect detection has nowhere to go, ideally it's done by a single MO, but if it
        # goes in DeviceManager it results in 6 different fn chains of DM -> Device -> ABS,
        # which goes unused by probably every other reservable. if this causes performance issues,
        # or another reservable needs this behavior , i think i'll make the MO a global?

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context, source="kernel")
        monitor.filter_by("usb", device_type="usb_device")
        self.observer = pyudev.MonitorObserver(monitor, lambda x, y : self.handleKernel(x, y), name=f"usbip-disconnect-detection-{self.getSerial()}")
        self.observer.start()

    def start(self):
        devs = get_devs().get(self.getSerial())
        if not devs:
            return

        for file in devs:
            if self.isSwitching():
                return

            self.handleAdd(file)

    def handleAdd(self, dev: dict):
        path = dev.get("DEVPATH")
        if not path:
            return

        busid = get_busid(path)

        if not busid:
            self.getLogger().warning(f"failed to get busid: {dev.get('DEVNAME')}")
            return

        self.busid = busid

        binded = usbip_bind(busid)

        if not binded:
            self.getLogger().warning("failed to bind device")
            return

        self.getLogger().debug(f"now exporting on bus {busid}")

        if not self.notif.export(busid, self.getConfig().getVirtualIp(), PORT):
            self.getLogger().debug(f"failed to send export event (bus {busid})")

    def handleKernel(self, event: str, dev: dict):
        if event != "remove":
            return

        path = dev.get("DEVPATH")

        if not path:
            return

        busid = get_busid(path)

        if not busid:
            self.getLogger().debug(f"failed to parse busid on kernel remove (devpath: {path})")
            return

        if busid != self.busid:
            return

        self.getLogger().warning(f"disconnected from usbip (bus: {busid})")
        self.notif.disconnect()

    @AbstractState.register("unbind")
    def unbind(self):
        if not self.busid:
            self.getLogger().warning("unbind request but no busid")
            return

        if not usbip_unbind(self.busid):
            self.getLogger().warning(f"failed to unbind on request - bus {self.busid}")
            return False

        return True

    def handleExit(self):
        super().handleExit()
        if not usbip_unbind(self.busid):
            self.getLogger().error(f"failed to unbind on exit - bus {self.busid}")

        self.observer.stop()

class UsbipEventSender:
    def __init__(self, device: Device):
        self.notif = device.getEventSender()
        self.serial = device.getSerial()

    def export(self, busid: str, ip: str, usbip_port: int):
        """Event signifies that a bus is now available through usbip
        for the client to connect to."""
        return self.notif.sendDeviceEvent({
            "event": "export",
            "busid": busid,
            "server_ip": ip,
            "usbip_port": usbip_port,

        })

    def disconnect(self):
        """Event signifies that the worker has detected a usbip disconnection
        for this serial. This detection is often delayed - it is possible that
        when a device is disconnected and then reconnected, the client receives
        the export event before the disconnect one."""
        return self.notif.sendDeviceEvent({"event": "disconnect"})
