from __future__ import annotations
import threading
import uuid
from typing import Dict, List

from usbipice.client.lib.pulsecount import PulseCountBaseClient, PulseCountEventHandler
from usbipice.client.lib import register
from usbipice.client.lib.utils import LoggerEventHandler, ReservationExtender

class PulseCountClient(PulseCountBaseClient):
    # TODO threadsafe evals
    """NOTE: this implementation is intended only for single threaded use.
        Evaluates bitstreams for pulse counts. Evaluation is done on each device."""
    def __init__(self, url, client_name, logger, log_events=False):
        super().__init__(url, client_name, logger)

        if log_events:
            self.addEventHandler(LoggerEventHandler(self.server, logger))

        self.addEventHandler(ReservationExtender(self.server, self, logger))
        self.addEventHandler(ResultHandler(self.server, self))

        self.cv = threading.Condition()
        self.results = {}
        self.uuid_map = {}
        self.remaining_serials = set()

    def _addResult(self, serial, value):
        with self.cv:
            self.results[serial] = value
            self.remaining_serials.remove(serial)

            if not self.remaining_serials:
                self.cv.notify_all()

    def evaluate(self, bitstream_paths: List[str]) -> Dict[Dict[str, int]]:
        "Evaluates a list of bitstream paths on each device. Returns as {serial -> {path -> pulses}}."
        self.uuid_map = {}
        self.results = {}
        self.remaining_serials = set()

        for path in bitstream_paths:
            self.uuid_map[str(uuid.uuid4())] = path

        self.remaining_serials = self.getSerials()

        super().evaluate(self.getSerials(), self.uuid_map)

        with self.cv:
            if self.remaining_serials:
                self.cv.wait_for(lambda : not self.remaining_serials)

        values = {}

        for key, value in self.results.items():
            paths = map(self.uuid_map.get, value.keys())
            values[key] = dict(zip(paths, value.values()))

        return values

class ResultHandler(PulseCountEventHandler):
    def __init__(self, event_server, client: PulseCountClient):
        super().__init__(event_server)
        self.client = client

    @register("results", "serial", "results")
    def results(self, serial: str, results: Dict[str, int]):
        self.client._addResult(serial, results)
