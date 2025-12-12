from logging import Logger

from usbipice.client.lib import BaseAPI, SocketEventServer, AbstractEventHandler

class BaseClient(BaseAPI):
    def __init__(self, url: str, client_name: str, logger: Logger):
        super().__init__(url, client_name, logger)
        self.server = SocketEventServer(client_name, [], logger)

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

            self.server.connectWorker(f"http://{info.ip}:{info.server_port}")
            connected.append(serial)

        return connected

    def requestWorker(self, serial: str, data: dict):
        """Sends data to socket of worker hosting serial. Note that the key client_id is overridden."""
        info = self.getConnectionInfo(serial)
        if not info:
            return False

        self.server.sendWorker(f"http://{info.ip}:{info.port}", "request", data)

    def stop(self):
        self.server.exit()
        self.endAll()
