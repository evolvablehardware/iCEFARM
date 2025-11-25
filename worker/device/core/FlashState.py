import os

from worker.device.core import AbstractState
from worker.device.core import BrokenState
from utils.dev import send_bootloader, upload_firmware_path

class FlashState(AbstractState):
    def __init__(self, state, mount_location, firmware_path, next_state_factory):
        super().__init__(state)
        self.mount_location = mount_location
        self.firmware_path = firmware_path
        self.next_state_factory = next_state_factory

        self.exiting = False

    def handleAdd(self, dev):
        devname = dev.get("DEVNAME")

        if not devname:
            self.getLogger().warning("add event with no devname")
            return

        if dev.get("SUBSYSTEM") == "tty":
            self.getLogger().debug("sending bootloader signal")
            send_bootloader(devname)
            return

        if dev.get("DEVTYPE") == "partition":
            self.getLogger().debug("found bootloader candidate")

            path = os.path.join(self.mount_location, self.getSerial())
            if not os.path.isdir(path):
                os.mkdir(path)

            uploaded = upload_firmware_path(devname, path, self.firmware_path)

            if not uploaded:
                self.getLogger().error("failed to upload firmware")
                self.switch(lambda : BrokenState(self.state))
                return

            self.switch(self.next_state_factory)
