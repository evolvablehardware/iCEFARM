from __future__ import annotations
from logging import Logger, LoggerAdapter
import threading
import time

import requests
import schedule

from usbipice.control import ControlDatabase

import typing
if typing.TYPE_CHECKING:
    from usbipice.control import ControlEventSender

# TODO get values from config
class HeartbeatConfig:
    def __init__(self):
        self.heartbeat_poll_seconds = 15
        self.timeout_poll_seconds = 15
        self.timeout_duration_seconds = 60
        self.reservation_poll_seconds = 30
        self.reservation_expiring_poll_seconds = 300
        self.reservation_expiring_notify_at_seconds = 20 * 60

    def getHeartbeatPoll(self):
        return self.heartbeat_poll_seconds

    def getTimeoutPoll(self):
        return self.timeout_poll_seconds

    def getTimeoutDuration(self):
        return self.timeout_duration_seconds

    def getReservationPoll(self):
        return self.reservation_poll_seconds

    def getReservationExpiringPoll(self):
        return self.reservation_expiring_poll_seconds

    def getReservationNotifyAt(self):
        return self.reservation_expiring_notify_at_seconds

class HeartbeatLogger(LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return f"[Heartbeat] {msg}", kwargs

class Heartbeat:
    def __init__(self, event_sender: ControlEventSender, database_url: str, config: HeartbeatConfig, logger: Logger):
        self.event_sender = event_sender
        self.logger = HeartbeatLogger(logger)
        self.database = ControlDatabase(database_url)
        self.config = config
        self.thread = None

    def start(self):
        self.__startHeartBeatWorkers()
        self.__startWorkerTimeouts()
        self.__startReservationTimeouts()
        self.__startReservationEndingSoon()

        def run():
            while True:
                schedule.run_pending()
                time.sleep(1)

        self.thread = threading.Thread(target=run, daemon=True, name="heartbeat")
        self.thread.start()

    # TODO duplicated from control.Control
    # not sure where to put this
    def __notifyEnd(self, client_id: str, worker_url: str, serial: str):
        self.event_sender.sendDeviceReservationEnd(serial, client_id)

        try:
            res = requests.get(f"{worker_url}/unreserve", json={
                "serial": serial
            }, timeout=10)

            if res.status_code != 200:
                self.logger.warning(f"[Control] failed to send unreserve command to worker {worker_url} device {serial}")
        except Exception:
            pass

    def __startHeartBeatWorkers(self):
        def do():
            def run():
                workers = self.database.getWorkers()

                if not workers:
                    return

                for row in workers:
                    name = row["name"]
                    ip = row["ip"]
                    port = row["port"]

                    url = f"http://{ip}:{port}/heartbeat"
                    try:
                        req = requests.get(url, timeout=10)

                        if req.status_code != 200:
                            raise Exception
                    except Exception:
                        self.logger.error(f"{name} failed heartbeat check")
                    else:
                        if not self.database.heartbeatWorker(name):
                            self.logger.error(f"failed to update heartbeat for {name}")
                        else:
                            self.logger.debug(f"heartbeat success for {name}")

            threading.Thread(target=run, name="heartbeat-worker", daemon=True).start()

        schedule.every(self.config.getHeartbeatPoll()).seconds.do(do)

    def __startWorkerTimeouts(self):
        def do():
            def run(timeout_dur=self.config.getTimeoutDuration()):
                data = self.database.getWorkerTimeouts(timeout_dur)
                if not data:
                    return

                for row in data:
                    self.event_sender.sendDeviceFailure(row["serial"], row["client_id"])
                    self.logger.info(f"Worker {row['worker']} failed; sent device failure for client {row['client_id']} device {row['serial']}")

            threading.Thread(target=run, name="heartbeat-worker-timeouts", daemon=True).start()

        schedule.every(self.config.getTimeoutPoll()).seconds.do(do)

    def __startReservationTimeouts(self):
        def do():
            def run():
                if not (data := self.database.getReservationTimeouts()):
                    return

                for row in data:
                    self.__notifyEnd(row["serial"], row["workerip"], row["workerport"])
                    self.logger.info(f"Reservation for device {row['serial']} by client {row['client_id']} ended")

            threading.Thread(target=run, name="heartbeat-reservation-timeouts", daemon=True).start()

        schedule.every(self.config.getReservationPoll()).seconds.do(do)

    def __startReservationEndingSoon(self):
        def do():
            def run(notify_at=self.config.getReservationNotifyAt()):
                if not (data := self.database.getReservationEndingSoon(notify_at)):
                    return

                for serial in data:
                    self.event_sender.sendDeviceReservationEndingSoon(serial)
                    self.logger.info(f"Sent ending soon notification for {serial}")

            threading.Thread(target=run, name="heartbeat-reservation-ending-soon", daemon=True).start()

        schedule.every(self.config.getReservationPoll()).seconds.do(do)
