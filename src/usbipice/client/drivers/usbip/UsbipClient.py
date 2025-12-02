from usbipice.client.lib import EventServer, AbstractEventHandler
from usbipice.client.drivers.usbip import UsbipHandler
from usbipice.client.lib.usbip import UsbipAPI
from usbipice.client.utils import DefaultEventHandler

class UsbipClient(UsbipAPI):
    def __init__(self, control_url, client_name, logger):
        super().__init__(control_url, client_name, logger)

        self.server = EventServer(logger)
        self.running = False

        default = DefaultEventHandler(self.server, self, logger)
        usbip = UsbipHandler(self.server, self, logger)

        self.eh = [default, usbip]

    def getEventServer(self) -> EventServer:
        return self.server

    def reserve(self, amount):
        if not self.running:
            raise Exception("Event server not started.")

        return super().reserve(amount, self.server.getUrl())

    def start(self, client_ip: str, client_port: str, event_handlers: list[AbstractEventHandler]=None):
        if event_handlers:
            for handler in event_handlers:
                self.eh.append(handler)

        self.server.start(client_ip, client_port, self.eh)
        self.running = True

    def stop(self):
        self.server.stop()
        self.running = False
        self.endAll()
