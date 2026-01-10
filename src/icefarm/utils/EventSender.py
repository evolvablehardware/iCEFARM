from __future__ import annotations
import logging
import threading
import json

import psycopg
from flask_socketio import SocketIO

from icefarm.utils import Database

class EventSenderLogger(logging.LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return f"[EventSender] {msg}", kwargs

class SessionLogger(logging.LoggerAdapter):
    def __init__(self, logger, client_id, extra = None):
        super().__init__(logger, extra)
        self.client_id = client_id

    def process(self, msg, kwargs):
        return f"[{self.client_id}] {msg}", kwargs

class Session:
    def __init__(self, socketio: SocketIO, event_sender, logger: logging.Logger, client_id: str):
        self.socketio = socketio
        self.event_sender = event_sender
        self.logger = SessionLogger(logger, client_id)
        self.client_id = client_id

        self.sock_id = None
        self.message_queue = []

        self.lock = threading.Lock()
        self.timeout = None

        self.startTimeout()

    def startTimeout(self, time: int=60):
        def timeout():
            self.logger.error("client did not connect in time")
            self.event_sender.endSession(self.client_id)

        with self.lock:
            self.timeout = threading.Timer(time, timeout)
            self.timeout.daemon = True
            self.timeout.name = f"socket-session-{self.client_id}-timeout-monitor"
            self.timeout.start()

    def stopTimeout(self):
        with self.lock:
            if self.timeout:
                self.timeout.cancel()

    def send(self, data: str):
        with self.lock:
            self.message_queue.append(data)
        self.flush()

    def setSocket(self, sock_id):
        with self.lock:
            self.sock_id = sock_id
        self.logger.info("socket connected")

        self.stopTimeout()
        self.flush()

    def removeSocket(self):
        with self.lock:
            self.sock_id = None
        self.logger.info("socket disconnected")

        self.startTimeout()

    def flush(self):
        with self.lock:
            if not self.message_queue:
                return

            if not self.sock_id:
                self.logger.warning("no socket to flush to")
                return

            messages, self.message_queue = self.message_queue, []
            sock_id = self.sock_id

        for message in messages:
            try:
                self.socketio.emit("event", message, to=sock_id)
                self.socketio.sleep(0)
            except Exception:
                self.logger.warning("socket disconnected during flush")
                with self.lock:
                    self.message_queue.append(message)
                    return

        self.logger.debug(f"flushed {len(messages)} events")

class EventSender(Database):
    def __init__(self, socketio: SocketIO, dburl: str, logger: logging.Logger):
        super().__init__(dburl)
        self.socketio = socketio
        self.logger = EventSenderLogger(logger)

        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()

    def startSession(self, client_id):
        with self.lock:
            if client_id not in self.sessions:
                self.sessions[client_id] = Session(self.socketio, self, self.logger, client_id)

            return self.sessions.get(client_id)

        self.logger.info(f"started session {client_id}")

    def addSocket(self, sock_id, client_id: str):
        session = self.startSession(client_id)
        session.setSocket(sock_id)

    def removeSocket(self, client_id):
        with self.lock:
            session = self.sessions.get(client_id)

        if session:
            session.removeSocket()
        else:
            self.logger.error(f"tried to socket for {client_id} but session does not exist")

    def endSession(self, client_id):
        with self.lock:
            self.sessions.pop(client_id, None)

    # TODO should probably use a database interface instead
    def __getReservationClientId(self, serial: str):
        """Returns the event server url for a device, None if there is none, or False on error."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM get_device_callback(%s::varchar(255))", (serial,))
                    data = cur.fetchall()
        except Exception:
            self.logger.warning(f"failed to get device callback for serial {serial}")
            return False

        if not data:
            # no reservation
            return None

        return data[0][0]

    def sendClient(self, client_id: str, contents: str):
        session = self.startSession(client_id)
        session.send(contents)

    def sendSerial(self, serial, contents: str):
        client_id = self.__getReservationClientId(serial)
        if not client_id:
            self.logger.warning(f"tried to send event to {serial} but no reservation")
            return

        return self.sendClient(client_id, contents)

    def __packageContents(self, serial: str, contents: dict):
        contents["serial"] = serial
        contents = {
            "serial": serial,
            "contents": contents
        }
        try:
            return json.dumps(contents)
        except Exception:
            return False

    def sendClientJson(self, serial: str, client_id: str, contents: dict) -> bool:
        contents = self.__packageContents(serial, contents)
        if not contents:
            return False

        self.sendClient(client_id, contents)
        return True

    def sendSerialJson(self, serial: str, contents: dict) -> bool:
        contents = self.__packageContents(serial, contents)
        if not contents:
            return False

        self.sendSerial(serial, contents)
        return True
