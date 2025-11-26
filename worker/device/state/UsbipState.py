from worker.device.state import AbstractState
from utils.dev import get_devs, get_busid
from utils.usbip import usbip_bind, usbip_unbind

class UsbipState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.busid = None
        self.getLogger().debug("now usbip state")

        devs = get_devs().get(self.getSerial())
        if not devs:
            return

        for file in devs:
            self.handleAdd(file)

    def handleAdd(self, dev):
        busid = get_busid(dev)

        if not busid:
            self.getLogger().warning(f"failed to get busid: {dev.get("DEVNAME")}")
            return

        self.busid = busid

        binded = usbip_bind(busid)

        if not binded:
            self.getLogger().warning("failed to bind device")

        self.getDatabase().updateDeviceBus(self.getSerial(), busid)
        if not self.getNotif().sendDeviceExport(self.getSerial(), busid):
            self.getLogger().debug("failed to send export event")

        self.getLogger().debug(f"now exporting on bus {busid}")

    @AbstractState.register("unbind")
    def unbind(self):
        if not self.busid:
            self.getLogger().warning("unbind request but no busid")
            return

        if not usbip_unbind(self.busid):
            self.getLogger().warning(f"failed to unbind on request - bus {self.busid}")

    def handleRemove(self, dev):
        pass

    def handleExit(self):
        if not usbip_unbind(self.busid):
            self.getLogger().error(f"failed to unbind on exit - bus {self.busid}")
