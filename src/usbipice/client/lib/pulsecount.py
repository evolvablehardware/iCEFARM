from __future__ import annotations
import uuid
from usbipice.client.lib import AbstractEventHandler, register, BaseClient

class PulseCountEventHandler(AbstractEventHandler):
    @register("results", "serial", "results")
    def results(self, serial: str, results: dict[str, int]):
        """Called when ALL bitstreams have been evaluated. Results maps
        from the file parameter used in the request body to the
        pulse amount."""

class PulseCountBaseClient(BaseClient):
    def reserve(self, amount):
        return super().reserve(amount, "pulsecount", {})

    def evaluate(self, serial: str, bitstreams: dict[uuid.UUID, str]):
        """Queues bitstreams for evaluations on device serial. Identifiers are used when
        sending back the results - these should be unique and not reused."""

        files = {}
        for iden, path in bitstreams.items():
            with open(path, "rb") as f:
                files[str(iden)] = f.read().decode("cp437")

        res = self.requestWorker(serial, {
            "serial": serial,
            "event": "evaluate",
            "contents": {
                "files": files
            }
        })

        return res
