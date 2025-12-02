import uuid
from usbipice.client.lib import AbstractEventHandler, register, BaseAPI

class PulseCountEventHandler(AbstractEventHandler):
    @register("results", "serial", "results")
    def results(self, serial: str, results: dict[str, int]):
        """Called when ALL bitstreams have been evaluated. Results maps
        from the file parameter used in the request body to the 
        pulse amount."""

class PulseCountAPI(BaseAPI):
    def reserve(self, amount, subscription_url):
        return super().reserve(amount, subscription_url, "pulsecount", {})

    def evaluate(self, serial: str, bitstreams: dict[uuid.UUID, str]):
        """Queues bitstreams for evaluations on device serial. Identifiers are used when 
        sending back the results - these should be unique and not reused."""

        files = {}
        for iden, path in bitstreams.items():
            files[iden] = open(path, "rb")

        res = self.requestWorker(serial, "/request", {
            "serial": serial,
            "event": "evaluate"
        }, files=files)

        # files closed by requests

        return res
