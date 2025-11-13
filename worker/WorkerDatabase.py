import psycopg
import requests

from utils.Database import Database

class WorkerDatabase(Database):
    def __init__(self, dburl: str, clientname: str, exported_ip: str, exported_server_port: int, exported_usbip_port: int, logger):
        super().__init__(dburl)
        self.clientname = clientname
        self.logger = logger

        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL addWorker(%s::varchar(255), %s::inet, %s::int, %s::int)", (clientname, exported_ip, exported_usbip_port, exported_server_port))
                    conn.commit()

        except Exception:
            logger.critical("Failed to add worker to database")
            raise Exception("Failed to add worker to database")

    
    def addDevice(self, deviceserial):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL addDevice(%s::varchar(255), %s::varchar(255))", (deviceserial, self.clientname))
                    conn.commit()
        except Exception:
            self.logger.error(f"database: failed to add device with serial {deviceserial}")
            return False
        
        return True
        
    def updateDeviceBus(self, deviceserial, bus):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL updateDeviceBus(%s::varchar(255), %s::varchar(10))", (deviceserial, bus))
                    conn.commit()
        except Exception:
            self.logger.error(f"database: failed to update bus to {bus} on device {deviceserial}")
            return False
        
        return True
    
    def sendDeviceSubscription(self, deviceserial, contents):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM getDeviceCallback(%s::varchar(255))", (deviceserial,))
                    data = cur.fetchall()
        except Exception:
            self.logger.error(f"failed to get device callback for serial {deviceserial}")
            return False

        if not data:
            self.logger.debug(f"device subscription update for {deviceserial} but no reservation")
            return
        
        url = data[0][0]

        try:
            requests.get(url, json=contents)
        except Exception:
            self.logger.warning(f"failed to send subscription update for {deviceserial} to {url}")
        else:
            self.logger.debug(f"sent subscription update for {deviceserial} to {url}")

    def removeDeviceBus(self, deviceserial):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL removeDeviceBus(%s::varchar(255))", (deviceserial,))
                    conn.commit()
        except Exception:
            self.logger.error(f"database: failed to remove bus on device {deviceserial}")
            return False
        
        return True

    def updateDeviceStatus(self, deviceserial, status):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL updateDeviceStatus(%s::varchar(255), %s::DeviceState)", (deviceserial, status))
                    conn.commit()
        except Exception:
            self.logger.error(f"database: failed to update device {deviceserial} to status {status}")
            return False
    
    def onExit(self):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM removeWorker(%s::varchar(255))", (self.clientname,))
                    data = cur.fetchall()
        except Exception:
            self.logger.warning("failed to remove worker from db before exit")
            return
        
        for row in data:
            url, serial = row

            try:
                requests.get(url, data={
                    "event": "failure",
                    "serial": serial
                })
            except:
                self.logger.warning(f"failed to notify {url} of device {serial} failure")
