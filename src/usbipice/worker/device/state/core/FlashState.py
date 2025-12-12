import threading

from usbipice.worker.device.state.core import AbstractState, BrokenState

from usbipice.utils.dev import send_bootloader, upload_firmware_path, get_devs

class FlashState(AbstractState):
    def __init__(self, state, firmware_path, next_state_factory, timeout=None):
        super().__init__(state)
        self.firmware_path = firmware_path
        self.next_state_factory = next_state_factory
        self.timer = None

        if timeout:
            def do_timeout():
                self.logger.error("flashing timed out")
                self.switch(lambda : BrokenState(self.getDevice()))

            self.timer = threading.Timer(timeout, do_timeout)
            self.timer.daemon = True
            self.timer.name = f"{self.getSerial()}-flash-timeout"
            self.timer.start()

    def start(self):
        devs = get_devs().get(self.getSerial())
        if not devs:
            return

        for file in devs:
            if self.isSwitching():
                return

            self.handleAdd(file)

    def handleAdd(self, dev):
        devname = dev.get("DEVNAME")

        if not devname:
            self.getLogger().warning("add event with no devname")
            return

        if dev.get("SUBSYSTEM") == "tty":
            self.getLogger().debug(f"sending bootloader signal to {devname}")
            send_bootloader(devname)
            return

        if dev.get("DEVTYPE") == "partition":
            self.getLogger().debug(f"found bootloader candidate {devname}")

            uploaded = upload_firmware_path(devname, self.getDevice().getMountPath(), self.firmware_path)

            if not uploaded:
                self.getLogger().error(f"failed to upload firmware to {devname}")
                if self.timer:
                    self.timer.cancel()
                self.switch(lambda : BrokenState(self.getDevice()))
                return

            if self.timer:
                self.timer.cancel()
            self.switch(self.next_state_factory)
