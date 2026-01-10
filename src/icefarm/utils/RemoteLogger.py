import threading
import time
import logging
from logging import Logger

import requests

class RemoteLogger:
    """Drop in replacement for a logging.Logger to also post to logs control server."""
    def __init__(self, logger: Logger, control_server: str, client_name: str, interval: int=30):
        self.logger: Logger = logger

        self.control_server = control_server
        self.client_name = client_name
        self.interval = interval

        self._backlog = []
        self._backlog_lock = threading.Lock()

        self._thread = threading.Thread(target=self._send, name="remote-logger", daemon=True)
        self._thread.start()

    def _send(self):
        while True:
            time.sleep(self.interval)
            with self._backlog_lock:
                logs = self._backlog
                self._backlog = []

            if not logs:
                continue

            try:
                res = requests.get(f"{self.control_server}/log", json={
                    "logs": logs,
                    "name": self.client_name
                }, timeout=10)
                if res.status_code != 200:
                    raise Exception
            except Exception:
                self.logger.error("[RemoteLogger] failed to send log results")

    def __getattr__(self, attr):
        # can't inherit from logging.Logger since its an externally managed singleton
        return getattr(self.logger, attr)

    def log(self, level, msg, *args, **kwargs):
        self.logger.log(level, msg, *args, **kwargs)
        with self._backlog_lock:
            self._backlog.append((level, msg))

    def debug(self, msg, *args, **kwargs):
        self.log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.log(logging.CRITICAL, msg, *args, **kwargs)
