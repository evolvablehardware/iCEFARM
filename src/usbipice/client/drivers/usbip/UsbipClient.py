from usbipice.client.drivers.usbip import UsbipHandler
from usbipice.client.lib.usbip import UsbipBaseClient
from usbipice.client.utils import DefaultEventHandler

class UsbipClient(UsbipBaseClient):
    """Maintains a consistent usbip connection. Automatically reconnects to devices that temporarily stop exporting a device path."""
    def __init__(self, control_url, client_name, logger):
        super().__init__(control_url, client_name, logger)

        self.addEventHandler(DefaultEventHandler(self.server, self, logger))
        self.addEventHandler(UsbipHandler(self.server, self, logger))
