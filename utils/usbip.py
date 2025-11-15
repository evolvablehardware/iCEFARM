import re
import subprocess

def usbipd(timeout=5):
    try:
        subprocess.run(["sudo", "usbipd", "-D"], timeout=timeout)
    except Exception:
        pass

def usbip_bind(busid, timeout=10):
    try:
        p = subprocess.run(["sudo", "usbip", "bind", "-b", busid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    except Exception:
        return False
    return p.returncode == 0

def usbip_unbind(busid, timeout=10):
    try:
        p = subprocess.run(["sudo", "usbip", "unbind", "-b", busid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    except Exception:
        return False
    return p.returncode == 0

def usbip_attach(ip, busid, tcp_port="3240", timeout=20):
    try:
        p = subprocess.run(["sudo", "usbip", "--tcp-port", str(tcp_port), "attach", "-r", ip, "-b", busid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
        if p.returncode != 0:
            raise Exception
    except Exception:
        return False

    return True

def usbip_port(timeout=20):
    try:
        p = subprocess.run(["sudo", "usbip", "port"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout)
        if p.returncode != 0:
            raise Exception
        
        connections = re.findall("usbip://.*?[0-9]+-(?:[0-9]|\\.)+", str(p.stdout))

        info = {}

        for c in connections:
            ip = re.search("usbip://(.*?):_list ", c)
            bus = re.search(":[0-9]+/(.*)", c)

            if not ip or not bus:
                return
            
            if ip not in info:
                info[ip] = []
            
            info[ip].append(bus)
        
        return info

    except Exception:
        return False

def get_exported_buses(timeout=10):
    try:
        p = subprocess.run(["usbip", "list", "-r", "localhost"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout)
    except Exception:
        return False

    if p.returncode != 0:
        return False

    return re.findall("([0-9]+-(?:[0-9]|\\.)+):", str(p.stdout))