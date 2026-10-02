import functools
from contextlib import contextmanager

from icefarm.client.drivers import PulseCountClient, VarMaxClient

@contextmanager
def get_client(control_url, name, logger, kind, devices=1, available_timeout=60):
    """Enables the use of with syntax:
    >>> with get_client(*args) as client:
            client.evaluateEach(BITSTREAM_PATHS)
    """
    if kind == "pulsecount":
        client = PulseCountClient(control_url, name, logger)
    elif kind == "varmax":
        client = VarMaxClient(control_url, name, logger)
    serials = client.reserve(devices, available_timeout=available_timeout)

    if not serials:
        raise Exception("Failed to reserve any devices")
    if len(serials) != devices:
        raise Exception(f"Tried to reserve {devices} devices but only got {len(serials)}")

    try:
        yield client

    except Exception as e:
        raise e
    finally:
        client.stop()
        if client.getSerials():
            raise Exception("Failed to end all reservations")

def get_client_partial(control_url, name, logger, kind, available_timeout=60):
    """Creates a ClientContext factory that does not require arguments
    >>> client_fac = get_client_partial(*args)
    >>> with client_fac() as client:
            client.evaluateEach(BITSTREAM_PATHS)
    """
    return functools.partial(get_client, control_url, name, logger, kind, available_timeout=available_timeout)
