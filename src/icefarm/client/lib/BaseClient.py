from __future__ import annotations
from logging import Logger
from typing import List
from itertools import groupby
import threading

from icefarm.client.lib import BaseAPI, EventServer, AbstractEventHandler, register
from icefarm.client.lib.utils import AvailabilityWaiter

class BaseClientEventHandler(AbstractEventHandler):
    """
    Updates the available serials on a client as reservations end and devices fail. Provides initialization
    detection for devices.
    """
    def __init__(self, event_server, client: BaseAPI):
        super().__init__(event_server)
        self.client = client
        self.recently_added_serials = []
        self.awaiting_serials = set()
        self.cond = threading.Condition()

    @register("reservation end", "serial")
    def handleReservationEnd(self, serial: str):
        self.client.removeSerial(serial)
        self.client.logger.warning(f"reservation for {serial} ended")

    @register("failure", "serial")
    def handleFailure(self, serial: str):
        self.client.removeSerial(serial)
        self.client.logger.warning(f"device {serial} failed")

    @register("initialized", "serial")
    def handleInitialization(self, serial):
        with self.cond:
            self.awaiting_serials.discard(serial)
            if not self.awaiting_serials:
                self.cond.notify_all()

    def waitUntilInitilized(self, serials):
        """Returns once 'initalized' events have been received for all the serials."""
        self.awaiting_serials = set(serials)

        with self.cond:
            for serial in self.recently_added_serials:
                self.awaiting_serials.pop(serial, None)

            if self.awaiting_serials:
                self.cond.wait_for(lambda : not self.awaiting_serials)

class BaseClient(BaseAPI):
    """Stitches the iCEFARM control server API and EventServer together to enable full management of devices."""
    def __init__(self, url: str, client_name: str, logger: Logger):
        super().__init__(url, client_name, logger)
        self.server = EventServer(client_name, [], logger)

        self.eh = BaseClientEventHandler(self.server, self)
        self.addEventHandler(self.eh)

        self.waiter = AvailabilityWaiter(self.server, self)
        self.addEventHandler(self.waiter)

        self.server.connectControl(url)

        # TODO track multiple initializations
        self.reservation_lock = threading.Lock()

    def addEventHandler(self, eh: AbstractEventHandler):
        self.server.addEventHandler(eh)

    def reserve(self, amount: int, kind: str, args: str, wait_for_available=False, available_timeout=None):
        """
        Reserves amount devices of type kind providing args to the worker when it is initilized. If wait_for_available,
        the client will wait until enough devices are available in the iCEFARM system. Otherwise, if there are not enough
        devices available, an error will be raised.
        """
        if self.available() < amount:
            if not wait_for_available:
                raise Exception("Not enough devices available")

            self.logger.warning("Not enough devices available, waiting for availability.")

            def raise_():
                raise Exception("Reservation timeout")

            if available_timeout:
                timer = threading.Timer(available_timeout, raise_)
                timer.daemon = True
                timer.name = "reserve-timeout-monitor"
                timer.start()

            self.waiter.waitForAmountAvailable(amount)
            if available_timeout:
                timer.cancel()

        with self.reservation_lock:
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

            self.eh.waitUntilInitilized(connected)
            return connected

    def reserveSpecific(self, serials, kind, args):
        """Reserves specific serials from the iCEFARM system. The serials must be available."""
        serials = super().reserveSpecific(serials, kind, args)

        if not serials:
            return serials

        connected = []

        for serial in serials:
            info = self.getConnectionInfo(serial)

            if not info:
                self.logger.error(f"could not get connection info for serial {serial}")

            self.server.connectWorker(info.url())
            connected.append(serial)

        self.eh.waitUntilInitilized(connected)
        return connected

    def removeSerial(self, serial):
        conn_info = self.getConnectionInfo(serial)
        super().removeSerial(serial)

        if not conn_info:
            return

        if not self.usingConnection(conn_info):
            self.server.disconnectWorker(conn_info.url())

    def requestWorker(self, serial: str, event: str, data: dict):
        """Sends data to socket of worker hosting serial. Note that the 'serial'
        field of the data will be override. If you want to duplicate requests across
        multiple serials, use requestBatchWorker instead.
        """
        info = self.getConnectionInfo(serial)
        if not info:
            return False

        return self.server.sendWorker(info.url(), "request", {
            "serial": serial,
            "event": event,
            "contents": data
        })

    def requestBatchWorker(self, serials: List[str], event: str, data: dict) -> List[str]:
        """Sends request to a list of serials. When the request is evaluated by the worker, the
        'serial' field is replaced. Returns serials included in requests to workers that failed.
        """
        failed_serials = []

        groups = groupby(serials, self.getConnectionInfo)

        for info, serials_iter in groups:
            batch_serials = list(serials_iter)

            if not info:
                self.logger.error(f"Could not get connection info for batch request serials: {batch_serials}")
                continue

            if not self.server.sendWorker(info.url(), "request", {
                "serial": batch_serials,
                "event": event,
                "contents": data
            }):
                self.logger.error(f"Failed to send request to worker {info.url()} for serials {batch_serials}")
                failed_serials.extend(batch_serials)

        return failed_serials

    def stop(self):
        self.server.exit()
        self.endAll()
