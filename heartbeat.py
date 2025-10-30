import psycopg
import logging
import sys
import os
import requests
from threading import Thread
import schedule

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
if not DATABASE_URL:
    logger.critical("USBIPICE_DATABASE not configured")
    raise Exception("USBIPICE_DATABASE not configured")

HEARTBEAT_TIME = os.environ.get("USBIPICE_HEARTBEAT_SECONDS")
if not HEARTBEAT_TIME:
    logger.warning("USBIPICE_HEARTBEAT_SECONDS not configured. Defaulting to 15s.")
    HEARTBEAT_TIME = 15

TIMEOUT_POLL = os.environ.get("USBIPICE_TIMEOUT_POLL_SECONDS")
if not TIMEOUT_POLL:
    logger.warning("USBIPICE_TIMEOUT_POLL_SECONDS not configured. Defaulting to 15s.")
    TIMEOUT_POLL = 15

TIMEOUT_DURATION = os.environ.get("USBIPICE_TIMEOUT_DURATION_SECONDS")
if not TIMEOUT_DURATION:
    logger.warning("USBIPICE_HEARTBEAT_TIMEOUT_SECONDS not configured. Defaulting to 60s.")
    TIMEOUT_DURATION = 60

RESERVATION_POLL = os.environ.get("USBIPICE_RESERVATION_POLL")
if not RESERVATION_POLL:
    logger.warning("USBIPICE_RESERVATION_POLL not configured. Defaulting to 30s")
    RESERVATION_POLL = 30

try:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            pass

except Exception:
    logger.critical("Failed to connect to database")
    raise Exception("Failed to connect to database")

def heartbeat_worker(name, ip, port):
    url = f"http://{ip}:{port}/heartbeat"
    try:
        requests.get(url)
    except:
        logger.warning(f"{name} failed heartbeat check")
    else:
        try:
            with psycopg.connect(url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL heartbeatWorker(%s::nvarchar(255))", (name,))
        except:
            logger.error(f"failed to update heartbeat on {name}")

def query_workers():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM WorkerHeartbeats")
                data = cur.fetchall()
        
        list(map(lambda x : heartbeat_worker(*x), data))

    except:
        logger.error("failed to query for workers")

def notify_device_timeout(url, serial):
    if not url:
        return
    
    try:
        requests.get(url, data={
            "event": "failure",
            "serial": serial
        })
    except:
        logger.warning(f"failed to notify {url} of timeout {serial}")

def worker_timeouts():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM handleWorkerTimeouts(%s::int)", (TIMEOUT_DURATION,))
                data = cur.fetchall()
        
        list(map(lambda x : notify_device_timeout(x[1], x[2]), data))

    except:
        logger.error("failed to get worker timeouts")

def reservation_notification(serial, url):
    if not url:
        return

    try:
        requests.get(url, data={
            "event": "reservation end",
            "serial": serial 
        })
    except:
        logger.warning(f"failed to notify {url} of device {serial} reservation ending")

def reservation_timeouts():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM handleReservationTimeouts()")

                data = cur.fetchall()
        
        list(map(lambda x : reservation_notification(x[0], x[1]), data))

    except:
        logger.error("failed to check for reservation timeouts")
        return

schedule.every(TIMEOUT_POLL).seconds.do(lambda : Thread(target=worker_timeouts).start())
schedule.every(HEARTBEAT_TIME).seconds.do(lambda : Thread(target=query_workers).start())
schedule.every(RESERVATION_POLL).seconds.do(lambda : Thread(target=reservation_timeouts).start())

while True:
    schedule.run_pending()







