"""
Utility functions that don't fit the other modules.
"""
from logging import Logger
import re
import subprocess
import os

from pexpect import fdpexpect

def get_env_default(var, default: str, logger: Logger):
    """Obtains an environment variable. If its not configured, it instead returns 
    the default value and logs a warning message."""
    value = os.environ.get(var)

    if not value:
        value = default
        logger.warning(f"{var} not configured, defaulting to {default}")

    return value

def check_default(devpath) -> bool:
    """Checks for whether a device is running the default firmware."""
    # TODO 
    # Sometimes closing the fd takes a long time (> 10s) on some firmwares,
    # this might create issues. I'm not really sure what the cause is, I added 
    # a read from stdio to the default firmware and it seems to fix the issue.
    # The same behavior happens from opening and closing the file in C.
    try:
        with open(devpath, "r") as f:
            p = fdpexpect.fdspawn(f, timeout=2)
            p.expect("default firmware", timeout=2)

    except Exception:
        return False

    return True

def get_ip() -> str:
    """Obtains local network ip from hostname -I."""
    res = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
    group = re.search("[0-9]{3}\\.[0-9]{3}\\.[0-9]\\.[0-9]{3}", str(res))
    if group:
        return group.group(0)

