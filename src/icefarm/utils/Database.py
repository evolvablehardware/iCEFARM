import json
import threading
from typing import List

import psycopg
from psycopg.types.enum import Enum, EnumInfo, register_enum

class DeviceStatus(Enum):
    available = 0
    reserved = 1
    await_flash_default = 2
    flashing_default = 3
    testing = 4
    broken = 5

class Database:
    """Base database class that syncs postgres enums with psycopg"""
    def __init__(self, dburl: str):
        self.url = dburl

        try:
            with psycopg.connect(self.url) as conn:
                info = EnumInfo.fetch(conn, "devicestatus")
                register_enum(info, conn, DeviceStatus)

        except Exception:
            raise Exception("Failed to connect to database")

    def execute(self, sql: str, args: tuple):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, args)
                    if sql[0:4] != "CALL":
                        return cur.fetchall()

                    return True
        except Exception:
            return False

    def proc(self, sql: str, args: tuple):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, args)
        except Exception:
            return False

        return True

    def getData(self, sql: str, args: tuple, columns: List[str], stringify=[]):
        if (data := self.execute(sql, args)) is False:
            return False

        out = list(map(lambda row : dict(zip(columns, row)), data))

        if stringify:
            for i, row in enumerate(out):
                for col in stringify:
                    out[i][col] = str(row[col])

        return out

    def listenReservations(self, callback):
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

    def listenAvailable(self, callback):
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

        threading.Thread(target=l, daemon=True, name="devies-available-listener").start()
