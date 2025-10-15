import re
import subprocess
import threading

def format_dev_file(udevinfo):
    id_serial = udevinfo.get("ID_SERIAL")
    usb_num = udevinfo.get("ID_USB_INTERFACE_NUM")
    dev_name = udevinfo.get("DEVNAME")
    dev_path = udevinfo.get("DEVPATH")
    return f"[{id_serial} : {usb_num} : {dev_name} : {dev_path}]"

def get_exported_buses():
    # this is dumb but -local includes devices that are not bound
    # if it doesn't work there are bigger issues
    p = subprocess.run(["usbip", "list", "-r", "localhost"], stdout=subprocess.PIPE, timeout=5)

    if p.returncode != 0:
        return False

    return re.findall("([0-9]+-[0-9]+):", str(p.stdout))

# some devices like disks will show up as multiple devices since there are
# also partitions, but these will have the same busid. If one of these are 
# exported using usbip, a future exports will cause an error
def get_busid(udevinfo):
    dev_path = udevinfo.get("DEVPATH")

    if not dev_path:
        return None
    
    capture = re.search("/usb1/(.*?)/", dev_path).group(1)
    busid = re.search("(.*?)-", capture).group(1)
    busid = int(float(busid))

    devid = re.search("-(.*?)$", capture).group(1)
    devid = int(float(devid))

    return f"{busid}-{devid}"

def usbip_bind(busid):
    p = subprocess.run(["sudo", "usbip", "bind", "-b", busid])
    return p.returncode == 0

def usbip_unbind(busid):
    p = subprocess.run(["sudo", "usbip", "unbind", "-b", busid])
    return p.returncode == 0

def send_bootloader(path, timeout=10):
    def send():
        subprocess.run(["sudo", "picocom", "--baud", "1200", path], timeout=timeout)
    
    t = threading.Thread(None, send)
    t.start()

def mount(drive, loc):
    p = subprocess.run(["sudo", "mount", drive, loc])
    return p.returncode == 0

def umount(loc):
    p = subprocess.run(["sudo", "umount", loc])
    return p.returncode == 0

