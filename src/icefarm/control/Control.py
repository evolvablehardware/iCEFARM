from __future__ import annotations
from logging import Logger
import threading

import requests

from icefarm.control import ControlDatabase
from icefarm.control.webapp import build_page

import typing
if typing.TYPE_CHECKING:
    from icefarm.control import ControlEventSender

class Control:
    def __init__(self, event_sender: ControlEventSender, database_url: str, logger: Logger):
        self.event_sender = event_sender
        self.database = ControlDatabase(database_url)
        self.logger = logger

        def update_available(amount):
            self.event_sender.sendAll({
                "event": "devices_available",
                "amount": amount
            })

        self.database.listenAvailable(update_available)
        self.database.listenReservations(self.event_sender.sendDeviceReservationEnd)

    # TODO this feels out of place
    def getApp(self):
        return build_page(self.database)

    def extend(self, client_id: str, serials: list[str]) -> list[str]:
        return self.database.extend(client_id, serials)

    def extendAll(self, client_id: str) -> list[str]:
        return self.database.extendAll(client_id)

    def reboot(self, serials: list[str]):
        out = []
        for serial in serials:
            if not (url := self.database.getDeviceWorkerUrl(serial)):
                return False

            try:
                res = requests.get(f"{url}/reboot", json={
                    "serial": serial
                }, timeout=10)

                if res.status_code != 200:
                    raise Exception

                out.append(serial)

            except Exception:
                self.logger.warning(f"[Control] failed to send reboot command to worker {url} device {serial}")

        return out

    def delete(self, serials: list[str]):
        out = []
        for serial in serials:
            if not (url := self.database.getDeviceWorkerUrl(serial)):
                return False

            try:
                res = requests.get(f"{url}/delete", json={
                    "serial": serial
                    }, timeout=10)

                if res.status_code != 200:
                    raise Exception

                out.append(serial)
            except Exception:
                self.logger.warning(f"[Control] failed to send delete command to worker {url} device {serial}")

        return out

    def end(self, client_id: str, serials: list[str]) -> list[str]:
        data = self.database.end(client_id, serials)
        return list(map(lambda row : row["serial"], data))


    def endAll(self, client_id: str) -> list[str]:
        data = self.database.endAll(client_id)
        return list(map(lambda row : row["serial"], data))

    def getAvailable(self):
        if (amount := self.database.getDevicesAvailable()) is False:
            return False

        return {
            "amount": amount
        }

    def reserve(self, client_id: str, amount: int, kind:str, args: dict) -> dict:
        if (con_info := self.database.reserve(amount, client_id, kind)) is False:
            return False

        for row in con_info:
            def send_reserve():
                ip = row["ip"]
                port = row["serverport"]
                serial = row["serial"]

                try:
                    res = requests.get(f"http://{ip}:{port}/reserve", json={
                        "serial": serial,
                        "kind": kind,
                        "args": args
                    }, timeout=15)

                    if res.status_code != 200:
                        raise Exception
                except Exception:
                    pass

            thread = threading.Thread(target=send_reserve, name="send-reservation")
            thread.start()

        return con_info
