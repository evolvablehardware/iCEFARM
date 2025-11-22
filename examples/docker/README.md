# Using the client with Docker
Running: 
```
docker run --rm -t -i --privileged -v /dev:/dev -v /lib/modules:/lib/modules --network=host -it usbipice bash
```
The -t, --privileged, and -v /dev:/dev flags provides access and passthrough to device files. The -v /lib/modules:/lib/modules allow access to kernel modules for usbip. In order for the kernel modules to work properly, the base image needs to run on the same kernel version as the host computer. The linux-tools-generic package installed in the image also must be the same version as the kernel.