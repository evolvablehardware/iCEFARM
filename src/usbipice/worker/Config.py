from configparser import ConfigParser
import os

from usbipice.utils import config_else_env
from usbipice.utils import get_ip

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

        self.name = config_else_env("USBIPICE_WORKER_NAME", "Connection", parser, error=False)
        if not self.name:
            self.name = os.environ.get("HOSTNAME")

        if not self.name:
            raise Exception("USBIPICE_WORKER_NAME not set, no HOSTNAME")

        print("WARNING: using {self.name}")


        self.port = config_else_env("USBIPICE_SERVER_PORT", "Connection", parser, default="8081")
        self.virtual_port = config_else_env("USBIPICE_VIRTUAL_PORT", "Connection", parser, default="8081")
        self.control = config_else_env("USBIPICE_CONTROL_SERVER", "Connection", parser)

        self.ip = config_else_env("USBIPICE_VIRTUAL_IP", "Connection", parser, error=False)
        if not self.ip:
            self.ip = get_ip()
            print(f"WARNING: using {self.ip}")

        self.database = os.environ.get("USBIPICE_DATABASE")
        if not self.database:
            raise Exception("Environment variable USBIPICE_DATABASE not configured. Set this to a libpg \
            connection string to the database. If using sudo .venv/bin/worker, you may have to use the ENV= sudo arguments.")

        self.default_firmware_path = config_else_env("USBIPICE_DEFAULT", "Firmware", parser)
        self.pulse_firmware_path = config_else_env("USBIPICE_PULSE_COUNT", "Firmware", parser)

    def getName(self):
        return self.name

    def getPort(self):
        return self.port

    def getVirtualIp(self):
        return self.ip

    def getVirtualPort(self):
        return self.virtual_port

    def getDatabase(self):
        return self.database

    def getDefaultFirmwarePath(self):
        return self.default_firmware_path

    def getPulseCountFirmwarePath(self):
        return self.pulse_firmware_path

    def getControl(self):
        return self.control
