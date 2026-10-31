from __future__ import annotations
import logging
import threading
import json
import uuid

from flask_socketio import SocketIO

from .Database import Database
from icefarm.utils import json_to_args

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
    """Manages messages for a specific iCEFARM client."""
    def __init__(self, socketio: SocketIO, event_sender: EventSender, logger: logging.Logger, client_id: str):
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
        """Starts session timeout. If a client with queued messages does not connect
        in time, the messages are discarded."""
        def timeout():
            self.logger.error("client did not connect in time")
            self.event_sender.endSession(self.client_id)

        with self.lock:
            self.timeout = threading.Timer(time, timeout)
            self.timeout.daemon = True
            self.timeout.name = f"socket-session-{self.client_id}-timeout-monitor"
            self.timeout.start()

    def stopTimeout(self):
        """Cancels timeout thread for use after successful flush"""
        with self.lock:
            if self.timeout:
                self.timeout.cancel()

    def send(self, data: str):
        """Adds packet to message queue"""
        with self.lock:
            self.message_queue.append(data)
        self.flush()

    def setSocket(self, sock_id):
        """Updates socket associated with the client, for use after socket connect"""
        with self.lock:
            self.sock_id = sock_id
        self.logger.info("socket connected")

        self.stopTimeout()
        self.flush()

    def removeSocket(self):
        """Removes socket associated with the client, for use after socket disconnect"""
        with self.lock:
            self.sock_id = None
        self.logger.info("socket disconnected")

        self.startTimeout()

    def flush(self):
        """Attempts to sent queued messages to client. Failed packets are added back
        into the message queue."""
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
                self.logger.debug(f"flushed message {message} to client {self.client_id}")
            except Exception:
                self.logger.warning("socket disconnected during flush")
                self.logger.debug(f"failed to flush message {message} to client {self.client_id}")
                with self.lock:
                    self.message_queue.append(message)

        self.logger.debug(f"flushed {len(messages)} events")

class BaseEvent:
    BASE_EVENT_CLS_ARGS = {}
    BASE_EVENT_CLS_SELF = {}

    def __init_subclass__(cls, register_args=None):
        super().__init_subclass__()
        # TODO can add dataclass decorator here, use those instead of register_args
        cls.BASE_EVENT_CLS_ARGS[cls.__name__] = register_args
        cls.BASE_EVENT_CLS_SELF[cls.__name__] = cls

    @classmethod
    def fromJson(cls, json):
        cls_name = json["format"]
        cls_args = cls.BASE_EVENT_CLS_ARGS[cls_name]
        cls_self = cls.BASE_EVENT_CLS_SELF[cls_name]
        event_contents = json["contents"]

        if set(cls_args) != set(event_contents.keys()):
            raise Exception("Arguments do not match parameters")

        args = json_to_args(event_contents, cls_args)
        return cls_self(*args)

    def toJson(self, senders: dict[str, uuid.UUID]) -> dict:
        contents = {}
        for atr in self.registered_args:
            contents[atr] = getattr(self, atr)

        return {
            "senders": senders,
            "format": type(self).__name__,
            "contents": contents

        }

class EventSender(Database):
    """Manages sending Events to clients using client_ids and serial reservation lookups.
    Routes messages to their respective websockets.
    Json format:
    ```json
    [
        {
            "senders": dict[Serial | "meta", uid]
            "format": class
            "contents": {}
        },
    ]
    ```
    Events are replicated for each destination listed in senders.
    """
    def __init__(self, socketio: SocketIO, dburl: str, logger: logging.Logger):
        super().__init__(dburl, logger)
        self.socketio = socketio
        self.logger = EventSenderLogger(logger)

        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()

    def startSession(self, client_id) -> Session:
        """Creates a Session with a client, or fetches an ongoing one, and returns it."""
        with self.lock:
            if client_id not in self.sessions:
                self.sessions[client_id] = Session(self.socketio, self, self.logger, client_id)
                self.logger.info(f"started session {client_id}")

            return self.sessions.get(client_id)

    def addSocket(self, sock_id, client_id: str):
        """Updates Session socket for a client"""
        session = self.startSession(client_id)
        session.setSocket(sock_id)

    def removeSocket(self, client_id):
        """Updates Session socket for a client"""
        with self.lock:
            session = self.sessions.get(client_id)

        if session:
            session.removeSocket()
        else:
            self.logger.error(f"tried to socket for {client_id} but session does not exist")

    # TODO cancel timeout, add logging
    def endSession(self, client_id):
        """Removes Session associated with client, discarding unsent messages."""
        with self.lock:
            self.sessions.pop(client_id, None)

    # NOTE this feels messy but this functionality doesn't seem to justify a separate Database class
    def __getReservationClientId(self, serial: str):
        """Returns the event server url for a device, None if there is none, or False on error."""
        if (data := self.execute("SELECT * FROM get_device_callback(%s::varchar(255))", (serial,))) is False:
            self.logger.warning(f"failed to get device callback for serial {serial}")
            return False

        if not data:
            return None

        return data[0][0]

    def sendClient(self, client_id: str, contents: str):
        """Sends contents to a client using client_id identifier."""
        session = self.startSession(client_id)
        session.send(contents)

    def sendSerial(self, serial, contents: str):
        """Sends content to client with an ongoing reservation for the serial device."""
        client_id = self.__getReservationClientId(serial)
        if not client_id:
            self.logger.warning(f"tried to send event to {serial} but no reservation")
            return

        return self.sendClient(client_id, contents)

    def sendAllJson(self, contents: dict):
        if not (contents := self.__packageContents("meta", contents)):
            return False

        sessions = list(self.sessions.values())
        for session in sessions:
            session.send(contents)

    def __packageContents(self, serial: str, contents: dict | list[dict]):
        if not isinstance(contents, list):
            contents = [contents]

        transformed = []

        for content in contents:
            transformed.append({
                "senders": [serial],
                "format": content["event"],
                "content": content
            })

        try:
            return json.dumps(transformed)
        except Exception:
            return False

    def sendClientJson(self, serial: str, client_id: str, contents: dict | list[dict]) -> bool:
        contents = self.__packageContents(serial, contents)
        if not contents:
            return False

        self.sendClient(client_id, contents)
        return True

    def sendSerialJson(self, serial: str, contents: dict | list[dict]) -> bool:
        contents = self.__packageContents(serial, contents)
        if not contents:
            return False

        self.sendSerial(serial, contents)
        return True
