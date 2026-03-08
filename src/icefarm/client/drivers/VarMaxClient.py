from __future__ import annotations
from icefarm.client.lib.varmax import VarMaxBaseClient
from icefarm.client.lib.utils import LoggerEventHandler, ReservationExtender

class VarMaxClient(VarMaxBaseClient):
    """Main client for variance maximization experiments."""
    def __init__(self, url, client_name, logger, log_events=False, send_waveform=False):
        super().__init__(url, client_name, logger)
        self.send_waveform = send_waveform

        self.addEventHandler(ReservationExtender(self.server, self, logger))
        if log_events:
            self.addEventHandler(LoggerEventHandler(self.server, logger))
