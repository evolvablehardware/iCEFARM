import functools
from usbipice.client.drivers import PulseCountClient

class ClientContext:
    """Context manager for PulseCountClient. Reserves devices on enter and
    ends reservations on exit.
    """
    def __init__(self, control_url, name, logger, devices):
        self.control_url = control_url
        self.name = name
        self.logger = logger
        self.devices = devices

        self.client = None

    def __enter__(self) -> PulseCountClient:
        self.client = PulseCountClient(self.control_url, self.name, self.logger)
        serials = self.client.reserve(self.devices)
        if not serials:
            raise Exception("Failed to reserve any devices")

        if len(serials) != self.devices:
            raise Exception(f"Tried to reserve {self.devices} devices but only got {len(serials)}")

        return self.client

    def __exit__(self, exc_type, exc_value, traceback):
        self.client.stop()
        if self.client.getSerials():
            raise Exception("Failed to end all reservations")

def get_client(control_url, name, logger, devices=1) -> ClientContext:
    """Enables the use of with syntax:
    >>> with get_client(*args) as client:
            client.evaluateEach(BITSTREAM_PATHS)
    """
    return ClientContext(control_url, name, logger, devices)

def get_client_partial(control_url, name, logger, devices=1):
    """Creates a ClientContext factory that does not require arguments
    >>> client_fac = get_client_partial(*args)
    >>> with client_fac() as client:
            client.evaluateEach(BITSTREAM_PATHS)
    """
    return functools.partial(get_client, control_url, name, logger, devices=devices)
