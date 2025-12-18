from __future__ import annotations
from logging import Logger

from usbipice.client.lib import BaseAPI, EventServer, AbstractEventHandler, register

class SerialRemover(AbstractEventHandler):
    """Calls BaseAPI.removeSerial when reservations and or devices fail."""
    def __init__(self, event_server, client: BaseAPI):
        super().__init__(event_server)
        self.client = client

    @register("reservation end", "serial")
    def handleReservationEnd(self, serial: str):
        self.client.removeSerial(serial)

    @register("failure", "serial")
    def handleFailure(self, serial: str):
        self.client.removeSerial(serial)

class BaseClient(BaseAPI):
    def __init__(self, url: str, client_name: str, logger: Logger):
        super().__init__(url, client_name, logger)
        self.server = EventServer(client_name, [], logger)
        self.addEventHandler(SerialRemover(self.server, self))
        self.server.connectControl(url)

    def addEventHandler(self, eh: AbstractEventHandler):
        self.server.addEventHandler(eh)

    def reserve(self, amount: int, kind: str, args: str):
        serials = super().reserve(amount, kind, args)

        if not serials:
            return serials

        connected = []

        for serial in serials:
            info = self.getConnectionInfo(serial)

            if not info:
                self.logger.error(f"could not get connection info for serial {serial}")

            self.server.connectWorker(info.url())
            connected.append(serial)

        return connected

    def removeSerial(self, serial):
        conn_info = self.getConnectionInfo(serial)
        super().removeSerial(serial)

        if not conn_info:
            return

        if not self.usingConnection(conn_info):
            self.server.disconnectWorker(conn_info.url())

    def requestWorker(self, serial: str, data: dict):
        """Sends data to socket of worker hosting serial. Note that the key client_id is overridden."""
        info = self.getConnectionInfo(serial)
        if not info:
            return False

        return self.server.sendWorker(info.url(), "request", data)

    def stop(self):
        self.server.exit()
        self.endAll()
