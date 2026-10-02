from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from psycopg.rows import class_row

from icefarm.utils import Database


class ControlDatabase(Database):
    @dataclass
    class _DeviceLocation:
        device_id: str
        wurl: str

    @dataclass
    class _Worker:
        id: str
        wurl: str
        heartbeat: Any
        farm_version: Any
        reservables: Any
        shutting_down: Any

    @dataclass
    class _Device:
        id: str
        worker_id: str
        device_status: Any
        client_id: Any

    @dataclass
    class _WorkerTimeout:
        serial_id: str
        client_id: str
        worker_id: str

    @dataclass
    class _ReservationTimeout:
        device_id: str
        client_id: str
        wurl: str

    def getDeviceWorkerUrl(self, serial: str) -> str:
        """Obtains the worker server url of the worker the device is located on."""
        if not (data := self.execute("SELECT * FROM get_device_worker(%s::varchar(255))", (serial,))):
            return False

        row = data[0][0]
        return row

    def reserve(self, amount: int, clientname: str, reservation_type: str) -> list[ControlDatabase._DeviceLocation]:
        """Reserves amount devices for clientname. Returns as {serial, url}"""
        return self.execute(
            "SELECT * FROM make_reservations(%s::int, %s::varchar(255), %s::varchar(255))", (amount, clientname, reservation_type),
            row_factory=class_row(self._DeviceLocation))

    def reserveSerials(self, client_id: str, serials: list[str], kind: str) -> list[_DeviceLocation]:
        return self.execute(
            "SELECT * FROM make_specific_reservations(%s::varchar(255), %s::varchar(255)[], %s::varchar(255))", (client_id, serials, kind),
            row_factory=class_row(self._DeviceLocation)
        )

    def extend(self, name: str, serials: list[str]) -> list[str]:
        """Extends the reservation time of the serials under the name of the client. Returns the extended serials"""
        data = self.execute("SELECT * FROM extend_reservations(%s::varchar(255), %s::varchar(255)[])", (name, serials))
        return data[0]

    def extendAll(self, name: str) -> list[str]:
        """Extends the reservation time of all serials under the name of the client. Returns the extended serials."""
        data = self.execute("SELECT * FROM extend_all_reservations(%s::varchar(255))", (name,))
        return data[0]

    def end(self, name: str, serials: list[str]) -> list[_DeviceLocation]:
        """Ends the reservation of serials under the name of the client.
        Returns as {serial, url}"""
        return self.execute(
            "select * from end_reservations(%s::varchar(255), %s::varchar(255)[])", (name, serials),
            row_factory=class_row(self._DeviceLocation)
        )

    def endAll(self, name: str) -> list[_DeviceLocation]:
        """Ends all of the reservations under the client name.
        Returns as {serial, url}"""
        return self.execute(
            "SELECT * FROM end_all_reservations(%s::varchar(255))", (name,),
            row_factory=class_row(self._DeviceLocation)
        )

    def getWorkers(self) -> list[_Worker]:
        """Gets information about all of the workers, returns as a list of {name, url}"""
        return self.execute(
            "SELECT * FROM worker", tuple(),
            row_factory=class_row(self._Worker)
        )

    def getDevices(self) -> list[_Device]:
        """Returns current devices, as a list of {serial, worker, status}."""
        return self.execute(
            "SELECT * FROM device_reservations", tuple(),
            row_factory=class_row(self._Device)
        )

    def heartbeatWorker(self, name: str):
        """Updates the last heartbeat time on a worker to the current time"""
        return self.proc("CALL heartbeat_worker(%s::varchar(255))", (name,))

    def getWorkerTimeouts(self, timeout_dur: int) -> list[_WorkerTimeout]:
        """Times out the workers that have not had a heartbeat in timeout_dur. Returns the
        timed out workers as a list of (serial, client_id, worker)."""
        return self.execute(
            "SELECT * FROM handle_worker_timeouts(%s::int)", (timeout_dur,),
            row_factory=class_row(self._WorkerTimeout)
        )

    def getReservationEndingSoon(self, minutes: int) -> list[str]:
        """Gets reservations that are ending soon, returns the serials."""
        data = self.execute("SELECT * FROM get_reservations_ending_soon(%s::int)", (minutes,))

        return list(map(lambda x : x[0], data))

    def getReservationTimeouts(self) -> list[_ReservationTimeout]:
        """Gets reservations that have timed out, returns (serial, client_id)"""
        return self.execute(
            "SELECT * FROM handle_reservation_timeouts()", tuple(),
            row_factory=class_row(self._ReservationTimeout)
        )

    def endAllReservations(self):
        """Deletes all reservations. Triggers reservation_end notification for each,
        causing workers to unreserve and reset devices."""
        self.proc("DELETE FROM reservations", tuple())

    def clearDevices(self):
        """Deletes all device records. Worker records are kept."""
        self.proc("DELETE FROM device", tuple())

    def clearWorkers(self):
        """Deletes all device and worker records. Device first due to FK constraint."""
        self.proc("DELETE FROM device", tuple())
        self.proc("DELETE FROM worker", tuple())

    def getAmountAvailable(self) -> int:
        data = self.execute("SELECT * FROM get_amount_available()", tuple())
        return data[0][0]

    def getDevicesAvailable(self) -> list[str]:
        data = self.execute("SELECT * FROM get_available_devices()", tuple())
        return [row[0] for row in data]
