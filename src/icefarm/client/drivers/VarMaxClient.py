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

    def reserve(self, amount, wait_for_available=False, available_timeout=60, kind="variance"):
        return super().reserve(amount, wait_for_available, available_timeout, kind, send_waveform=self.send_waveform)

    def reserveSpecific(self, serials, kind="variance"):
        return super().reserveSpecific(serials, kind, send_waveform=self.send_waveform)
