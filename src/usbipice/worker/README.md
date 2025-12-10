# Worker Setup

## Without Usbip - local
Set USBIPICE_DATABASE to the [libpg connection string](https://www.postgresql.org/docs/8.0/libpq.html) of the control database. Run ```docker compose up```.

## With Usbip - local
Usbip requires a host specific package to function. The usbip module can be installed with ```sudo apt install linux-tools-[kernel release]```. The kernel release can be found with ```uname -r```. Next, the usbip modules need to be loaded. These will have to be loaded again after a reboot.
```
sudo modprobe usbip_host
sudo modprobe usbip_core
sudo modprobe vhci_hcd
sudo usbipd -D
```

Now, an image specific to the host needs to be made starting from a reference. Either will work.
- [ubuntu questing 25.10 kernel 6.17.0-1004-raspi](./deploy/questing-rpi.dockerfile)
- [ubuntu noble 24.04 kernel 6.14.0-36-generic](./deploy/noble-generic.dockerfile)

First, the base image needs be modified to match the host. For example, ubuntu noble 24.04 uses the ubuntu:noble-20240423 image. Next, the linux-tools package edition that is installed in the image needs to be updated to the same one that was installed earlier on the host. Before building the image, follow the instructions in [firmware](./firmware/). After this is done, the image is ready to be built and should be done from the root of the project. Set USBIPICE_DATABASE to the [libpg connection string](https://www.postgresql.org/docs/8.0/libpq.html) of the control database. Deploy the container:
```
docker run --privileged -v /dev:/dev -v /lib/modules:/lib/modules -v /run/udev:/run/udev -v /tmp:/tmp -d --network=host -e USBIPICE_DATABASE="$USBIPICE_DATABASE" -e USBIPICE_WORKER_NAME="$USER" [IMAGE NAME] .venv/bin/worker -c src/usbipice/worker/example_config.ini
```

## Deploying
Using container orchestration software with usbip is still in progress. In the meanwhile, [deploy.py](./deploy/deploy.py) can be used for testing. This simply sshs into a list of hosts, pulls the image, and runs it.
