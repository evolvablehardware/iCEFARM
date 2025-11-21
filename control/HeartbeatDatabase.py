from logging import Logger

import psycopg

from utils.Database import Database

class HeartbeatDatabase(Database):
    def __init__(self, dburl: str, logger: Logger):
        super().__init__(dburl)
        self.logger = logger

    def getWorkers(self) -> list:
        """Gets information about all of the workers, returns as a list of (name, ip, port)"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM WorkerHeartbeats")
                    data = cur.fetchall()

            return data
        except Exception:
            self.logger.error("failed to query for workers")
            return None

    def heartbeatWorker(self, name: str):
        """Updates the last heartbeat time on a worker to the current time"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL heartbeatWorker(%s::varchar(255))", (name,))
        except Exception:
            self.logger.error(f"failed to update heartbeat on {name}")

    def getWorkerTimeouts(self, timeout_dur: int) -> list:
        """Times out the workers that have not had a heartbeat in timeout_dur. Returns the 
        timed out workers as a list of (serial, notificationurl)."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM handleWorkerTimeouts(%s::int)", (timeout_dur,))
                    data = cur.fetchall()

            return data
        except Exception:
            self.logger.error("failed to get worker timeouts")
            return None

    def getReservationEndingSoon(self, minutes: int) -> list[str]:
        """Gets reservations that are ending soon, returns the serials."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM getReservationsEndingSoon(%s::int)", (minutes,))

                    data = cur.fetchall()

            return data

        except Exception:
            self.logger.error("failed to check for reservation timeouts")
            return None

    def getReservationTimeouts(self) -> list[str]:
        """Gets reservations that have timed out, returns (serial, notificationurl)"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM handleReservationTimeouts()")

                    data = cur.fetchall()

            return data

        except Exception:
            self.logger.error("failed to check for reservation timeouts")
            return None
