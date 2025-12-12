import threading
import time
import logging

import requests

class RemoteLogger:
    """Drop in replacement for a logging.Logger to also post to logs control server."""
    def __init__(self, logger, control_server, client_name, interval=30):
        self.logger = logger

        self.control_server = control_server
        self.client_name = client_name
        self.interval = interval

        self.backlog = []
        self.backlog_lock = threading.Lock()

        self.thread = threading.Thread(target=self._send, name="remote-logger", daemon=True)
        self.thread.start()

    def getLogger(self) -> logging.Logger:
        return self.logger

    def _send(self):
        while True:
            time.sleep(self.interval)
            with self.backlog_lock:
                logs = self.backlog
                self.backlog = []

            if not logs:
                continue

            try:
                res = requests.get(f"{self.control_server}/log", json={
                    "logs": logs,
                    "name": self.client_name
                })
                if res.status_code != 200:
                    raise Exception
            except Exception:
                self.logger.error("[RemoteLogger] failed to send log results")

    def __getattr__(self, attr):
        # can't inherit from logging.Logger since its an externally managed singleton
        return getattr(self.logger, attr)

    def log(self, level, msg, *args, **kwargs):
        self.logger.log(level, msg, *args, **kwargs)
        with self.backlog_lock:
            self.backlog.append((level, msg))

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
