from __future__ import annotations
from usbipice.utils import Database

class ControlDatabase(Database):

    def getDeviceWorkerUrl(self, serial: str) -> str:
        """Obtains the worker server url of the worker the device is located on."""
        if not (data := self.execute("SELECT * FROM getDeviceWorker(%s::varchar(255))", (serial,))):
            return False

        row = data[0]
        ip, port = row[0], row[1]
        return f"http://{ip}:{port}"

    def reserve(self, amount: int, clientname: str, reservation_type: str) -> dict:
        """Reserves amount devices for clientname. Returns as {serial, ip, serverport}"""
        return self.getData(
            "SELECT * FROM makeReservations(%s::int, %s::varchar(255), %s::varchar(255))", (amount, clientname, reservation_type),
            ["serial", "ip", "serverport"], stringify=["ip"]
        )


    def extend(self, name: str, serials: list[str]) -> list[str]:
        """Extends the reservation time of the serials under the name of the client. Returns the extended serials"""
        return self.execute("SELECT * FROM extendReservations(%s::varchar(255), %s::varchar(255)[])", (name, serials))

    def extendAll(self, name: str) -> list[str]:
        """Extends the reservation time of all serials under the name of the client. Returns the extended serials."""
        return self.execute("SELECT * FROM extendAllReservations(%s::varchar(255))", (name,))

    def end(self, name: str, serials: list[str]):
        """Ends the reservation of serials under the name of the client.
        Returns as {serial, workerip, workerport}"""
        return self.getData(
            "select * from endReservations(%s::varchar(255), %s::varchar(255)[])", (name, serials),
            ["serial", "workerip", "workerport"], stringify=["workerip", "workerport"]
        )

    def endAll(self, name: str):
        """Ends all of the reservations under the client name.
        Returns as {serial, workerip, workerport}"""
        return self.getData(
            "SELECT * FROM endAllReservations(%s::varchar(255))", (name,),
            ["serial", "workerip", "workerport"], stringify=["workerip", "workerport"]
        )

    def getWorkers(self) -> dict:
        """Gets information about all of the workers, returns as a list of {name, ip, port}"""
        return self.getData(
            "SELECT * FROM Worker", tuple(),
            ["name", "ip", "port", "heartbeat", "version", "reservables", "shutting_down"], stringify=["ip", "port"]
        )

    def getDevices(self) -> dict:
        """Returns current devices, as a list of {serial, worker, status}."""
        return self.getData(
            "SELECT * FROM DeviceReservations", tuple(),
            ["serial", "worker", "status", "client_id"], stringify=["status"]
        )

    def heartbeatWorker(self, name: str):
        """Updates the last heartbeat time on a worker to the current time"""
        return self.proc("CALL heartbeatWorker(%s::varchar(255))", (name,))

    def getWorkerTimeouts(self, timeout_dur: int) -> list:
        """Times out the workers that have not had a heartbeat in timeout_dur. Returns the
        timed out workers as a list of (serial, client_id, worker)."""
        return self.getData(
            "SELECT * FROM handleWorkerTimeouts(%s::int)", (timeout_dur,),
            ["serial", "client_id", "worker"]
        )

    def getReservationEndingSoon(self, minutes: int) -> list[str]:
        """Gets reservations that are ending soon, returns the serials."""
        data = self.execute("SELECT * FROM getReservationsEndingSoon(%s::int)", (minutes,))
        if not data:
            return False

        return list(map(lambda x : x[0], data))

    def getReservationTimeouts(self) -> list[str]:
        """Gets reservations that have timed out, returns (serial, client_id)"""
        return self.getData(
            "SELECT * FROM handleReservationTimeouts()", tuple(),
            ["serial", "client_id", "workerip", "workerport"], stringify=["workerip", "workerport"]
        )
