# iCE FPGA Array Resource Manager
Device manager for reserving and interfacing with pico2-ice development boards.

## iCEFARM Setup
If you have access to an existing iCEFARM server, you do not need to do this. Setting up iCEFARM is only needed if you want to run locally. Linux is required to run the iCEFARM server (but not for interfacing with the system). It is tested on Ubuntu 24, but most distributions should work fine. Some older Ubuntu versions (<20) will not interact with the picos properly.

The picos need to be prepared by flashing firmware that is tinyusb enabled and being plugged in. The [rp2_hello_world](https://github.com/tinyvision-ai-inc/pico-ice-sdk/tree/main/examples/rp2_hello_world) example from the pico-ice-sdk works for this purpose. Picos can also be plugged into an iCEFARM system once it is already running.

Sometimes other packages can take control of the devices after they are plugged in. Verify that the dev files are present:
```ls /dev | grep ACM```
There should be one `ACM` device per pico when running the `rp2_hello_world` firmware.

Here are known problematic packages that may need to be removed:
- brltty
- modemmanager

Ensure that the usb cable is not power only. The `dmesg` output can also be used to try to determine problematic packages:
```sudo dmesg```

If it is not yet installed, install [Docker Engine](https://docs.docker.com/engine/install/). You may follow the [post installation steps](https://docs.docker.com/engine/install/linux-postinstall/) so that you do not need to use sudo, but note that this does enable privilege escalation. Included below:
```
sudo usermod -aG docker $USERNAME
#new shell or log out and then login
newgrp docker
```

Build the iCEFARM image. ~~You may skip this step and the image will automatically download from [DockerHub](https://hub.docker.com/r/evolvablehardware/icefarm)~~ (for now just build the image, investigating issue with dockerhub images).
```
docker build -f docker/Dockerfile -t evolvablehardware/icefarm:all .
```

If you do choose to skip this step, note that provided image does not automatically update after it is downloaded. In order to update the image in the future, it can be manually pulled:
```
docker pull evolvablehardware/icefarm:all
```

A docker compose file is provided, which allows the iCEFARM system to be quickly deployed. Start the iCEFARM system:
```
docker compose -f docker/compose.yml up
```
When you first start the stack, you should see a container named similarly to `db-1` start up. Afterwards, a container named similarly to `flyway-1` will start and then exit. Finally, the main iCEFARM `worker-1` and `control-1` containers will start.

You should see periodic pings between the control and worker:
```
worker-1   | INFO:     127.0.0.1:41132 - "GET /heartbeat HTTP/1.1" 200 OK
control-1  | [Control] [Heartbeat] heartbeat success for host_worker
```

You should also see a series of logs related to flashing any connected pico2ices. The actual output might not look like this exactly, but the device should eventually reach the `ReadyState`. There may be additional lines in between, and the `/dev` path may be different. There may also be multiple bootloader signals sent. If you have more than once device connected, you should see a variation of this output for each device, with the exception of the first and last lines.

```
[DeviceManager] Scanning for devices
[DeviceManager] [{SERIAL}] [FlashState] state is now FlashState
[DeviceManager] [{SERIAL}] [FlashState] sending bootloader signal to /dev/ttyACM0
[DeviceManager] [{SERIAL}] [TestState] state is now TestState
[DeviceManager] [{SERIAL}] [ReadyState] state is now ReadyState
[DeviceManager] Finished scan
```

There is a debug panel by located at ```http://localhost:8080``` by default. You should see a single worker listed, as well as an amount of available devices equal to the amount plugged in. The panel contains a variety of useful actions, but mostly the end reservation option. Sometimes devices may get stuck in a reserved state, which will result an error mentioning not enough devices available when running the client. This will mark the device as available again. In addition, the reboot option can be used to attempt to fix a malfunctioning device without interrupting an ongoing reservation.

If there is unexpected behavior, check the [troubleshooting](#troubleshooting) section.

The [pulse count example client](./examples/pulse_count_driver/pulse.py) can now be run. This uses the client to upload a 2Khz, 8Khz, and 32Khz circuit which iCEFARM measures the pulses of. Note that the exact amount of pulses reported may differ a few between runs. See the script itself for additional configuration options, such as compiling and evaluating arbitrary pulse circuits. At least python 3.12 should be used.

Start by creating a python venv:
```
python3 -m venv .venv
source .venv/bin/activate
```
Install iCEFARM as a package locally. This allows changes to the package to automatically be applied without having to repackage and install after each modification.
```
pip install -e .
```
The package can also be alternatively installed from [pypi](https://pypi.org/project/icefarm/). Run the example:
```
python examples/pulse_count_driver/pulse.py
```

Stop the stack:
```
docker compose -f docker/compose.yml down
```
Note that just using ```ctrl+c``` will not fully shutdown the stack and the database state will persist between runs, which will create issues.

### Troubleshooting
*Generally, most things by can be fixed by destroying the stack and starting it again*
#### Pico Light Status
Green: initialized
Blinking green: waiting for bitstream
Blue: receiving bitstream
Blue + red: flashing and evaluating
Blue + red + green: idle
Blinking red: usb disconnected

#### Accessing Logs
First, find the name of the worker and control container:
```docker container ls```
These are typically named `docker-worker-1` and `docker-control-1`.
Getting logs:
```
docker logs <worker name>
docker logs <control name>
```

#### Device goes to BrokenState
This can happen occasionally even if everything is set up correctly. Restart the stack and replug the device in. If it happens again, it's probably a configuration error. Verify that you are able to manually flash firmware on to the device with a baud 1200 compatible firmware:
```
sudo picocom --baud 1200 /dev/ttyACM0
sudo mount /dev/sda1 [mount_location]
sudo cp [firmware_location] [mount_location]
sudo umount [mount_location]
```
Note that you will have to wait between commands for the device to respond, and that the exact device path may be different.
