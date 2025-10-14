# usbip-ice
Device manager for exporting pico2-ice boards over usbip

## Setup usbip
```
sudo modprobe usbip_core
sudo modprobe usbip_host
sudo modprobe vhci_hcd
sudo usbipd -D
```

## API
**GET /devices/all**
Returns the serial ids of all devices in the system  
**GET /devices/available**
Returns the serial ids of all devices that are not marked as reserved  
**GET /devices/bus/\<device>**
Returns the busid being exported with usbip by the device  
**GET /devices/reserve/\<device>**
Mark a device id as reserved  
**GET /devices/unreserve/\<device>**
Unmark a device id as reserved  
**POST /devices/flash/\<device>**
Updates the firmware to that specified by the *firmware* file and *name* of the request body  
