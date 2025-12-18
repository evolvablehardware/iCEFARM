from __future__ import annotations
from logging import Logger

import requests

from usbipice.control import ControlDatabase

import typing
if typing.TYPE_CHECKING:
    from usbipice.control import ControlEventSender

class Control:
    def __init__(self, event_sender: ControlEventSender, database_url: str, logger: Logger):
        self.event_sender = event_sender
        self.database = ControlDatabase(database_url)
        self.logger = logger

    def extend(self, client_id: str, serials: list[str]) -> list[str]:
        return self.database.extend(client_id, serials)

    def extendAll(self, client_id: str) -> list[str]:
        return self.database.extendAll(client_id)

    def __notifyEnd(self, client_id: str, serial: str, worker_url: str):
        self.event_sender.sendDeviceReservationEnd(serial, client_id)

        try:
            res = requests.get(f"{worker_url}/unreserve", json={
                "serial": serial
            }, timeout=10)

            if res.status_code != 200:
                self.logger.warning(f"[Control] failed to send unreserve command to worker {worker_url} device {serial}")
        except Exception:
            pass

    def end(self, client_id: str, serials: list[str]) -> list[str]:
        data = self.database.end(client_id, serials)
        for row in data:
            self.__notifyEnd(client_id, row['serial'], f"http://{row['workerip']}:{row['workerport']}")

        return list(map(lambda row : row["serial"], data))


    def endAll(self, client_id: str) -> list[str]:
        data = self.database.endAll(client_id)
        for row in data:
            self.__notifyEnd(client_id, row["serial"], f"http://{row['workerip']}:{row['workerport']}")

        return list(map(lambda row : row["serial"], data))

    def reserve(self, client_id: str, amount: int, kind:str, args: dict) -> dict:
        if (con_info := self.database.reserve(amount, client_id)) is False:
            return False

        for row in con_info:
            ip = row["ip"]
            port = row["serverport"]
            serial = row["serial"]

            try:
                res = requests.get(f"http://{ip}:{port}/reserve", json={
                    "serial": serial,
                    "kind": kind,
                    "args": args
                }, timeout=5)

                if res.status_code != 200:
                    raise Exception
            except Exception:
                pass

        return con_info
