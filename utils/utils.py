import re
import subprocess
import threading
from pexpect import fdpexpect
import os

def get_env_default(var, default, logger):
    value = os.environ.get(var)

    if not value:
        value = default
        logger.warning(f"{var} not configured, defaulting to {default}")
    
    return value

def get_serial(dev):
    """Obtains the serial from a dev file dict. Returns false if the dev file 
    is not related to pico2-ice."""
    devname = dev.get("DEVNAME")

    if not devname:
        return False

    if not re.match("/dev/", devname) or re.match("/dev/bus/", devname):
        return False

    id_model = dev.get("ID_MODEL")

    if id_model != "RP2350" and id_model != 'pico-ice' and id_model != 'Pico':
        return False
    
    serial = dev.get("ID_SERIAL_SHORT")

    if serial:
        return serial
    
    return False

def check_default(devpath):
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

# theres no good way to get the host from uvicorn,
# since the application thread does not have access to the server object
# this seems to be the least hacky way to go about it
def getIp():
    res = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    return re.search("[0-9]{3}\\.[0-9]{3}\\.[0-9]\\.[0-9]{3}", str(res)).group(0)

def format_dev_file(udevinfo):
    id_serial = udevinfo.get("ID_SERIAL")
    usb_num = udevinfo.get("ID_USB_INTERFACE_NUM")
    dev_name = udevinfo.get("DEVNAME")
    dev_path = udevinfo.get("DEVPATH")
    return f"[{id_serial} : {usb_num} : {dev_name} : {dev_path}]"

class FirmwareUploadFail(Exception):
    def __init__(self, *args):
        super().__init__(*args)

def upload_firmware(partition_path, mount_location, firmware_bytes, mount_timeout=10):
    mounted = mount(partition_path, mount_location, timeout=mount_timeout)

    if not mounted:
        return False

    if os.listdir(mount_location) != ["INDEX.HTM", "INFO_UF2.TXT"]:
        umount(mount_location)
        return False

    try:
        with open(os.path.join(mount_location, "firmware.uf2"), "wb") as f:
            f.write(firmware_bytes)
    except Exception:
        umount(partition_path)
        raise FirmwareUploadFail()

    umount(partition_path)

    return True

def get_exported_buses():
    # this is dumb but -local includes devices that are not bound
    # if it doesn't work there are bigger issues
    try:
        p = subprocess.run(["usbip", "list", "-r", "localhost"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        return False

    if p.returncode != 0:
        return False

    return re.findall("([0-9]+-(?:[0-9]|\\.)+):", str(p.stdout))

# some devices like disks will show up as multiple devices since there are
# also partitions, but these will have the same busid. If one of these are 
# exported using usbip, a future exports will cause an error
def get_busid(udevinfo):
    dev_path = udevinfo.get("DEVPATH")

    if not dev_path:
        return None
    
    # TODO really need to find a better way to do this
    capture = re.search("/usb1/.*?/(.*?)([:/]|$)", dev_path)
    if capture:
        return capture.group(1)
    return None

def usbip_bind(busid):
    try:
        p = subprocess.run(["sudo", "usbip", "bind", "-b", busid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        return False
    return p.returncode == 0

def usbip_unbind(busid):
    try:
        p = subprocess.run(["sudo", "usbip", "unbind", "-b", busid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        return False
    return p.returncode == 0

def usbip_attach(ip, busid, tcp_port="3240"):
    try:
        p = subprocess.run(["sudo", "usbip", "--tcp-port", str(tcp_port), "attach", "-r", ip, "-b", busid], timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode != 0:
            raise Exception
    except:
        return False
    
    return True

def send_bootloader(path, timeout=10):
    try:
        p = subprocess.run(["sudo", "picocom", "--baud", "1200", path], timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return False
    
    return True

def mount(drive, loc, timeout=10):
    try:
        p = subprocess.run(["sudo", "mount", drive, loc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
        if p.returncode != 0:
            raise Exception
    except:
        return False
    
    return True

def umount(loc):
    try:
        p = subprocess.run(["sudo", "umount", loc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode != 0:
            raise Exception
    except:
        return False
    
    return True

