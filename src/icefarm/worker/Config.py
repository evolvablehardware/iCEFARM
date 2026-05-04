from __future__ import annotations
from configparser import ConfigParser
import os

from icefarm.utils import config_else_env
from icefarm.utils import get_ip

class Config:
    # TODO do logging here
    def __init__(self, path=None):
        if path:
            if not os.path.exists(path):
                raise Exception("Config file does not exist")

            parser = ConfigParser()
            parser.read(path)
        else:
            parser = None

        self.worker_name: str= config_else_env("ICEFARM_WORKER_NAME", "Connection", parser, error=False)
        if not self.worker_name:
            self.worker_name = os.environ.get("HOSTNAME")
            print(f"WARNING: using {self.worker_name}")

        if not self.worker_name:
            raise Exception("ICEFARM_WORKER_NAME not set, no HOSTNAME")

        self.worker_url: str = config_else_env("ICEFARM_WORKER_URL", "Connection", parser)
        self.control_server_url: str = config_else_env("ICEFARM_CONTROL_SERVER", "Connection", parser, error=False)
        if not self.worker_url:
            self.worker_url = "http://localhost:8081"
            print(f"WARNING: using {self.worker_url}")

        self.libpg_string= os.environ.get("ICEFARM_DATABASE")
        if not self.libpg_string:
            raise Exception("Environment variable ICEFARM_DATABASE not configured. Set this to a libpg \
            connection string to the database. If using sudo .venv/bin/worker, you may have to use the ENV= sudo arguments.")

        self.default_firmware_path = config_else_env("ICEFARM_DEFAULT", "Firmware", parser)
        self.pulse_firmware_path = config_else_env("ICEFARM_PULSE_COUNT", "Firmware", parser)
        self.variance_firmware_path = config_else_env("ICEFARM_VARIANCE", "Firmware", parser, error=False)
