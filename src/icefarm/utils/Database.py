import json
import threading
from typing import Callable, Any
from logging import Logger, LoggerAdapter

import psycopg
from psycopg.types.enum import Enum, EnumInfo, register_enum
class DeviceStatus(Enum):
    available = 0
    reserved = 1
    await_flash_default = 2
    flashing_default = 3
    testing = 4
    broken = 5

# TODO this needs general logging

class DatabaseException(Exception):
    pass

class DatabaseLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[Database] {msg}", kwargs
class Database:
    """Base database class that syncs postgres enums with psycopg"""
    def __init__(self, dburl: str, logger: Logger):
        self.url = dburl
        self._logger = DatabaseLogger(logger)

        try:
            with psycopg.connect(self.url) as conn:
                info = EnumInfo.fetch(conn, "devicestatus")
                register_enum(info, conn, DeviceStatus)

        except Exception:
            raise Exception("Failed to connect to database")

    def execute(self, sql: str, args: tuple, row_factory=None) -> Any:
        """Execute psycopg query with arguments, returning rows. Not suitable for calls without return values."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor(row_factory=row_factory) as cur:
                    cur.execute(sql, args)
                    return cur.fetchall()

        except Exception as e:
            self._logger.debug(f"failed to execute query: {sql}, args: {args}")
            raise DatabaseException(e)

    def proc(self, sql: str, args: tuple) -> bool:
        """Execute psycopg query with arguments"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, args)
        except Exception as e:
            self._logger.debug(f"failed to execute proc query: {sql}, args: {args}")
            raise DatabaseException(e)

        return True

    def listenReservations(self, callback: Callable[[str, str], None]):
        """Performs callback when a devices reservation ends, passing in [serial, client_id]."""
        def l():
            with psycopg.connect(self.url, autocommit=True) as conn:
                conn.execute("LISTEN reservation_updates")
                gen = conn.notifies()

                for notif in gen:
                    try:
                        js = json.loads(notif.payload)
                        callback(js["device_id"], js["client_id"])
                    except Exception:
                        pass

        threading.Thread(target=l, daemon=True, name="reservation-update-listener").start()

    def listenAvailable(self, callback: Callable[[int], None]):
        """Performs callback when the amount of available devices change, passing in the total number
        of available devices."""
        def l():
            with psycopg.connect(self.url, autocommit=True) as conn:
                conn.execute("LISTEN device_available")
                gen = conn.notifies()

                for notif in gen:
                    try:
                        amount = notif.payload[1:-1]
                        callback(int(amount))
                    except Exception:
                        pass

        threading.Thread(target=l, daemon=True, name="devices-available-listener").start()
