import threading

from icefarm.worker.device.state.core import AbstractState, BrokenState

from icefarm.utils.dev import send_bootloader, upload_firmware_path, get_devs

class FlashState(AbstractState):
    def __init__(self, state, firmware_path, next_state_factory, timeout=None):
        super().__init__(state)
        self.firmware_path = firmware_path
        self.next_state_factory = next_state_factory
        self.timer = None

        if timeout:
            def do_timeout():
                self.logger.error("flashing timed out")
                self.switch(lambda : BrokenState(self.device))

            self.timer = threading.Timer(timeout, do_timeout)
            self.timer.daemon = True
            self.timer.name = f"{self.serial}-flash-timeout"
            self.timer.start()

    def start(self):
        devs = get_devs().get(self.serial)
        if not devs:
            return

        for file in devs:
            if self.switching:
                return

            self.handleAdd(file)

    def handleAdd(self, dev):
        devname = dev.get("DEVNAME")

        if not devname:
            self.logger.warning("add event with no devname")
            return

        if dev.get("SUBSYSTEM") == "tty":
            self.logger.debug(f"sending bootloader signal to {devname}")
            send_bootloader(devname)
            return

        if dev.get("DEVTYPE") == "partition":
            self.logger.debug(f"found bootloader candidate {devname}")

            uploaded = upload_firmware_path(devname, self.device.mount_path, self.firmware_path)

            if not uploaded:
                self.logger.error(f"failed to upload firmware to {devname}")
                if self.timer:
                    self.timer.cancel()
                self.switch(lambda : BrokenState(self.device))
                return

            if self.timer:
                self.timer.cancel()
            self.switch(self.next_state_factory)
