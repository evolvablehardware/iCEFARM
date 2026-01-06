from __future__ import annotations
from collections.abc import Iterator
from dataclasses import dataclass
import json

import flask

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from usbipice.control import ControlDatabase

@dataclass
class WorkerRow:
    name: str
    url: str
    version: str
    shutting_down: str
    reservables_list: list[str]

    @property
    def reservables(self):
        if not self.reservables_list:
            return ""

        return ", ".join(self.reservables_list)

class Worker:
    def __init__(self, rows: Iterator[WorkerRow]):
        self.rows = list(rows)

    @property
    def online(self):
        return len(self.rows)

class DeviceRow:
    def __init__(self, serial, worker, status, client_id):
        self.serial = serial
        self.worker = worker
        self.status = status
        self.client_id = client_id

        js = "?json=" + json.dumps({
            "serials": [self.serial],
            "name": client_id
        })

        self.end_reservation = "./end" + js
        self.reboot = "./reboot" + js
        self.delete = "./delete" + js

class Device:
    def __init__(self, rows: Iterator[DeviceRow]):
        self.rows = list(rows)

    def filterStatus(self, status):
        return len(list(filter(lambda d : d.status == status, self.rows)))

    @property
    def total(self):
        return len(self.rows)

    @property
    def available(self):
        return self.filterStatus("available")

    @property
    def reserved(self):
        return self.filterStatus("reserved")

    @property
    def broken(self):
        return self.filterStatus("broken")

def build_page(database: ControlDatabase) -> str:
    try:
        if (worker_data := database.getWorkers()) is False:
            raise Exception

        worker = Worker(map(lambda r : WorkerRow(r["name"], f"http://{r["ip"]}:{r["port"]}", r["version"], r["shutting_down"], r["reservables"]), worker_data))

        if (device_data := database.getDevices()) is False:
            raise Exception

        device = Device(map(lambda r : DeviceRow(r["serial"], r["worker"], r["status"], r["client_id"]), device_data))

        return flask.render_template("home.html", workers=worker, devices=device)

    except Exception:
        return "Failed to fetch data"
