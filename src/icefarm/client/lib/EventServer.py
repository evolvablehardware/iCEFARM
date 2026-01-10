from __future__ import annotations
from logging import LoggerAdapter
import threading
import json

import socketio

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from icefarm.client.lib import AbstractEventHandler

class EventLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[EventServer] {msg}", kwargs

class SocketLogger(LoggerAdapter):
    def __init__(self, logger, url, extra = None):
        super().__init__(logger, extra)
        self.url = url

    def process(self, msg, kwargs):
        return f"[socket@{self.url}] {msg}", kwargs

class Event:
    def __init__(self, serial, event, contents):
        self.serial = serial
        self.event = event
        self.contents = contents

class EventServer:
    """Hosts a server for the workers and heartbeat process to send events to. When an event is received,
    it calls the corresponding method of the EventHandlers starting at the 0 index."""
    def __init__(self, client_id, eventhandlers: list[AbstractEventHandler], logger):
        self.client_id = client_id
        self.logger = EventLogger(logger)
        self.eventhandlers = eventhandlers

        self.worker_lock = threading.Lock()
        self.worker_sockets: dict[str, socketio.Client] = {}

        self.control_lock = threading.Lock()
        self.control_socket = None

    def addEventHandler(self, eh: AbstractEventHandler):
        """Adds an event handler. Should not be called after reservations have
        been made."""
        self.eventhandlers.append(eh)

    def handleEvent(self, event: Event):
        for eh in self.eventhandlers:
            eh.handleEvent(event)

    def __createSocket(self, url):
        sio = socketio.Client()

        logger = SocketLogger(self.logger, url)

        @sio.event
        def connect():
            logger.info("connected")
        @sio.event
        def connect_error(_):
            logger.error("connection attempt failed")
        @sio.event
        def disconnect(reason):
            logger.error(f"disconnected: {reason}")
        @sio.event
        def event(data):
            try:
                msg = json.loads(data)
            except Exception:
                logger.error("received unparsable data")
                return

            serial = msg.get("serial")
            contents = msg.get("contents")

            if contents:
                event = contents.get("event")
            else:
                event = None

            if not serial or not event or not contents:
                logger.error("bad event contents")
                return

            logger.debug(f"received {event} event")
            event = Event(serial, event, contents)
            self.handleEvent(event)

        # TODO
        try:
            sio.connect(url, auth={"client_id": self.client_id}, wait_timeout=10)
            return sio
        except Exception:
            return False

    def connectWorker(self, url):
        if not self.control_socket:
            raise Exception("Control socket not connected")
        with self.worker_lock:
            if url in self.worker_sockets:
                return

            self.worker_sockets[url] = self.__createSocket(url)

    def sendWorker(self, url, event, data: dict):
        """Sends data to worker socket."""
        try:
            data = json.dumps(data)
        except Exception:
            self.logger.error(f"failed to jsonify event {event} for worker {url}")
            return

        with self.worker_lock:
            sio = self.worker_sockets.get(url)

            if not sio:
                return False

            sio.emit(event, data)

            return True

    def connectControl(self, url):
        with self.control_lock:
            self.control_socket = self.__createSocket(url)

    def disconnectWorker(self, url):
        with self.worker_lock:
            sio = self.worker_sockets.get(url)

            if not sio:
                return True

            sio.disconnect()

            del self.worker_sockets[url]

    def exit(self):
        for eh in self.eventhandlers:
            eh.exit()

        with self.worker_lock:
            urls = list(self.worker_sockets)

        for url in urls:
            self.disconnectWorker(url)
