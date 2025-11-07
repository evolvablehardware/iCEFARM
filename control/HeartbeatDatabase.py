import psycopg

from utils.Database import Database

class HeartbeatDatabase(Database):
    def __init__(self, dburl: str, logger):
        super().__init__(dburl)
        self.logger = logger
    
    def getWorkers(self):
        """Returns as (name, ip, port)"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM WorkerHeartbeats")
                    data = cur.fetchall()
            
            return data
        except Exception:
            self.logger.error("failed to query for workers")
            return None

    def heartbeatWorker(self, name):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL heartbeatWorker(%s::nvarchar(255))", (name,))
        except Exception:
            self.logger.error(f"failed to update heartbeat on {name}")
    
    def getWorkerTimeouts(self, timeout_dur):
        """Returns as (worker, notificationurl, serial)"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM handleWorkerTimeouts(%s::int)", (timeout_dur,))
                    data = cur.fetchall()
            
            return data
        except Exception:
            self.logger.error("failed to get worker timeouts")
            return None

    def getReservationEndingSoon(self, minutes):
        """Returns as (serial, url)"""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM getReservationsEndingSoon(%s::int)", (minutes,))

                    data = cur.fetchall()
            
            return data
            
        except Exception:
            self.logger.error("failed to check for reservation timeouts")
            return None
    
    def getReservationTimeouts(self):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM handleReservationTimeouts()")

                    data = cur.fetchall()
            
            return data

        except Exception:
            self.logger.error("failed to check for reservation timeouts")
            return None
    
    
