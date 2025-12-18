# Worker Setup

You will want to pick ONLY one of the follow three options for setting up your workers:
* Local
* Docker without USBIP
* Docker with USBIP


## Local
First, setup the [control](../control/). Then, fill out a [configuration](#configuration). Install usbipice:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

If using with usbip, install and enable the usbip module:
```
sudo apt install "linux-tools-$(uname -r)"
sudo modprobe usbip_core
sudo modprobe usbip_host
sudo modprobe vhci_hcd
sudo modprobe usbipd -D
```
Note that the modules will need to be reloaded after a reboot. 
Set USBIPICE_DATABASE to the [libpg connection string](https://www.postgresql.org/docs/8.0/libpq.html) of the control database. 

Because of accessing the device, this requires running with sudo privileges. Here is the command to run:
```
sudo USBIPICE_DATABASE="$USBIPICE_DATABASE" .venv/bin/worker -c [path_to_config_file]
```
Note that if using additional environment variables instead of the configuration file, they will have to be transferred to the sudo environment (as shown above with setting USBIPICE_DATABASE).

After running the command above you should get an output like this:

```
$ [command from above]
Scanning for devices
Finished scan
```



## Docker - without usbip
- Install [docker engine](https://docs.docker.com/engine/install/)
- Set USBIPCE_CONTROL_SERVER to the url of the control server
- Set USBIPICE_DATABASE to the [libpg connection string](https://www.postgresql.org/docs/8.0/libpq.html) of the control database
- ```docker compose -f src/usbipice/worker/deploy/compose.yml up```

## Docker - with usbip
- Setup [control](../control/)
- Install [docker engine](https://docs.docker.com/engine/install/)
 - Hint: Set up Docker's apt repository first!

The usbip module is kernel specific:
```
sudo apt install "linux-tools-$(uname -r)"
```
Enable usbip:
```
sudo modprobe usbip_host
sudo modprobe usbip_core
sudo modprobe vhci_hcd
sudo usbipd -D
```
Note that the modules will need to be reloaded after a reboot. Now, an image specific to the host needs to be made starting from a reference. Either of the following images that are already into the repo will work.
- [ubuntu questing 25.10 kernel 6.17.0-1004-raspi](./deploy/questing-rpi.dockerfile)
- [ubuntu noble 24.04 kernel 6.14.0-36-generic](./deploy/noble-generic.dockerfile)

First, the base image needs be modified to match the host. For example, ubuntu noble 24.04 uses the ubuntu:noble-20240423 image. Next, the linux-tools package edition that is installed in the image needs to be updated to the same one that was installed earlier on the host. Before building the image, follow the instructions in [firmware](./firmware/). After this is done, the image is ready to be built and should be done from the root of the project.
- Set USBIPICE_DATABASE to the [libpg connection string](https://www.postgresql.org/docs/8.0/libpq.html) of the control database
- Set USBIPCE_CONTROL_SERVER to the url of the control server
 - Hint: You will not want to run with sudo, instead:
 ```
 sudo usermod -aG docker {linux-username}
 #new shell or log out and then login
 newgrp docker
 #this runs the worker
 docker compose -f src/usbipice/worker/deploy/compose.yml up
 ```
 #need to include host=[localhost]
export USBIPICE_DATABASE='host=[localhost] dbname=[db_name] user=[user] password=[pass]'


Run container:
```
docker run --privileged -v /dev:/dev -v /lib/modules:/lib/modules -v /run/udev:/run/udev -v /tmp:/tmp -d --network=host -e USBIPICE_DATABASE="$USBIPICE_DATABASE" -e USBIPICE_WORKER_NAME="$USER" -e USBIPICE_CONTROL_SERVER="$USBIPICE_CONTROL_SERVER" [IMAGE NAME] .venv/bin/worker -c src/usbipice/worker/example_config.ini
```
## Configuration
Configuration options, excluding USBIPICE_DATABASE, can be provided as a file using ```worker -c [path]```. An [example](./example_config.ini) is provided.
| Environment Variable | Description | Default |
|----------------------|-------------|---------|
|USBIPICE_DATABASE|[psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)| required |
|USBIPICE_WORKER_NAME| Name of the worker for identification purposes. Must be unique.| required|
|USBIPICE_CONTROL_SERVER | Url to control server | required |
|USBIPICE_DEFAULT| Path for Ready state firmware | required |
|USBIPICE_PULSE_COUNT | Path for PulseCount state firmware | required |
|USBIPICE_SERVER_PORT| Port to host server on | 8081|
|USBIPICE_VIRTUAL_IP| Ip for clients to reach worker with | First result from hostname -I |
|USBIPICE_VIRTUAL_PORT| Port for clients to reach worker with | 8081 |


## Building Images
- Available on [dockerhub](https://hub.docker.com/repository/docker/usbipiceproject/usbipice-worker/general)
- Prior to building, [firmware](./firmware/) must also be built
- Built from root directory

## Deploying
Using container orchestration software with usbip is still in progress. In the meanwhile, [deploy.py](./deploy/deploy.py) can be used for testing. This simply sshs into a list of hosts, pulls an image, and runs it.
