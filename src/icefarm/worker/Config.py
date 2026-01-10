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

        self.worker_name: str= config_else_env("USBIPICE_WORKER_NAME", "Connection", parser, error=False)
        if not self.worker_name:
            self.worker_name = os.environ.get("HOSTNAME")
            print(f"WARNING: using {self.worker_name}")

        if not self.worker_name:
            raise Exception("USBIPICE_WORKER_NAME not set, no HOSTNAME")

        self.server_port: str = config_else_env("USBIPICE_SERVER_PORT", "Connection", parser, default="8081")
        self.virtual_server_port: str = config_else_env("USBIPICE_VIRTUAL_PORT", "Connection", parser, default="8081")
        self.control_server_url: str = config_else_env("USBIPICE_CONTROL_SERVER", "Connection", parser, error=False)
        if not self.control_server_url:
            print("WARNING: not logging to control")
        self.virtual_ip: str = config_else_env("USBIPICE_VIRTUAL_IP", "Connection", parser, error=False)
        if not self.virtual_ip:
            self.virtual_ip = get_ip()
            print(f"WARNING: using {self.virtual_ip}")

        self.libpg_string= os.environ.get("USBIPICE_DATABASE")
        if not self.libpg_string:
            raise Exception("Environment variable USBIPICE_DATABASE not configured. Set this to a libpg \
            connection string to the database. If using sudo .venv/bin/worker, you may have to use the ENV= sudo arguments.")

        self.default_firmware_path = config_else_env("USBIPICE_DEFAULT", "Firmware", parser)
        self.pulse_firmware_path = config_else_env("USBIPICE_PULSE_COUNT", "Firmware", parser)
