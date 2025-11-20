# Client Usage

## Installation
Currently, Linux is required for the usbip module. If this is not already installed, it can be found in the linux-tools-generic package. After installation, enable the usbip related modules:
```
sudo modprobe usbip_core
sudo modprobe usbip_host
sudo modprobe vhci_hcd
```
Note that these modules will be unloaded after rebooting. Next, the client can be installed using pip:
```
python3 -m venv .venv
source .venv/bin/activate
pip install git+https://github.com/heiljj/usbip-ice.git
```

## Running
```
sudo USBIPICE_CONTROL_SERVER=[url] .venv/bin/usbipconnect [amount of devices] [client name] -f [firmware path] -i [ip for control to reach client at] -p [port to host event server on] 
```
The -f and -p flags are optional. If -i is not set, it will default to that of the local network. If you don't upload firmware to the device, it will print "default firmware" on the dev file ttyACMx. When the program is exited, it will unreserve and disconnect from the devices. If it doesn't exit after 3 seconds, you may have to exit again. Note that if you upload firmware, there will be messages about device disconnections. This is normal and happens when the device exposes the bootloader and during reboot. In high latency situations, usbip may experience a timeout. If this happens, the device should be reconnected to after a few seconds.











