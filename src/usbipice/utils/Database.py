import psycopg
from psycopg.types.enum import Enum, EnumInfo, register_enum
from typing import List

class DeviceState(Enum):
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
                info = EnumInfo.fetch(conn, "DeviceState")
                register_enum(info, conn, DeviceState)

        except Exception:
            raise Exception("Failed to connect to database")

    def execute(self, sql: str, args: tuple):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, args)
                    return cur.fetchall()
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
