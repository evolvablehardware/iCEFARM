import psycopg
from psycopg.types.enum import Enum, EnumInfo, register_enum
from enum import Enum
import requests

class DeviceState(Enum):
    available = 0
    reserved = 1
    await_flash_default = 2
    flashing_default = 3
    broken = 4

class Database:
    def __init__(self, dburl: str, clientname: str, exported_ip: str, exported_server_port: int, exported_usbip_port: int, logger):
        self.url = dburl
        self.clientname = clientname
        self.logger = logger

        try:
            with psycopg.connect(self.url) as conn:
                info = EnumInfo.fetch(conn, "DeviceState")
                register_enum(info, conn, DeviceState)

                with conn.cursor() as cur:
                    cur.execute("CALL addWorker(%s::varchar(255), %s::inet, %s::int, %s::int)", (clientname, exported_ip, exported_usbip_port, exported_server_port))
                    conn.commit()

        except Exception:
            logger.critical("Failed to connect to database")
            raise Exception("Failed to connect to database")

    
    def addDevice(self, deviceserial):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL addDevice(%s::varchar(255), %s::varchar(255))", (deviceserial, self.clientname))
                    conn.commit()
        except:
            self.logger.error(f"database: failed to add device with serial {deviceserial}")
            return False
        
        return True
        
    def updateDeviceBus(self, deviceserial, bus):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL updateDeviceBus(%s::varchar(255), %s::varchar(10))", (deviceserial, bus))
                    conn.commit()
        except:
            self.logger.error(f"database: failed to update bus to {bus} on device {deviceserial}")
            return False
        
        return True
    
    def removeDeviceBus(self, deviceserial):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL removeDeviceBus(%s::varchar(255))", (deviceserial,))
                    conn.commit()
        except Exception as e:
            self.logger.error(f"database: failed to remove bus on device {deviceserial}")
            return False
        
        return True

    def updateDeviceStatus(self, deviceserial, status):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL updateDeviceStatus(%s::varchar(255), %s::DeviceState)", (deviceserial, status))
                    conn.commit()
        except:
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
