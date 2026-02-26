from __future__ import annotations

from icefarm.client.lib.pulsecount import PulseCountBaseClient
from icefarm.client.lib.utils import LoggerEventHandler, ReservationExtender

# TODO not sure if the base design makes as much sense anymore,
# going to keep it around for now
class PulseCountClient(PulseCountBaseClient):
    """Main client for pulse count experiments."""
    def __init__(self, url, client_name, logger, log_events=False):
        super().__init__(url, client_name, logger)

        self.addEventHandler(ReservationExtender(self.server, self, logger))
        if log_events:
            self.addEventHandler(LoggerEventHandler(self.server, logger))
