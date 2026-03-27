# iCE FPGA Array Resource Manager
Device manager for reserving and interfacing with pico2-ice development boards.

## iCEFARM Setup
If you have access to an existing iCEFARM server, you do not need to do this. Setting up iCEFARM is only needed if you want to run locally. Linux is required to run the iCEFARM server (but not for interfacing with the system). It is tested on Ubuntu 24, but most distributions should work fine. Some older Ubuntu versions (<20) will not interact with the picos properly.

The picos need to be prepared by flashing firmware that is tinyusb enabled and being plugged in. The [rp2_hello_world](https://github.com/tinyvision-ai-inc/pico-ice-sdk/tree/main/examples/rp2_hello_world) example from the pico-ice-sdk works for this purpose. Picos can also be plugged into an iCEFARM system once it is already running.

Sometimes other packages can take control of the devices after they are plugged in. Verify that the dev files are present:
```bash
ls /dev | grep ACM
```
Example output:
```
ttyACM0
```

There should be one `ACM` device per pico when running the `rp2_hello_world` firmware.

Here are known problematic packages that may need to be removed:
- brltty
- modemmanager

Ensure that the usb cable is not power only. The `lsusb` command is useful to detect connected devices while `dmesg` provides a detailed log that can be used to determine problematic packages.

If it is not yet installed, install [Docker Engine](https://docs.docker.com/engine/install/). You may follow the [post installation steps](https://docs.docker.com/engine/install/linux-postinstall/) so that you do not need to use sudo, but note that this does enable privilege escalation. Included below:
```bash
sudo usermod -aG docker $USER
#new shell or log out and then login
newgrp docker
```

Build the iCEFARM image. You may skip this step and the image will automatically download from [DockerHub](https://hub.docker.com/r/evolvablehardware/icefarm).
```bash
docker build -f docker/Dockerfile -t evolvablehardware/icefarm:all .
```

If you do choose to skip this step, note that provided image does not automatically update after it is downloaded. In order to update the image in the future, it can be manually pulled:
```bash
docker pull evolvablehardware/icefarm:all
```

A docker compose file is provided, which allows the iCEFARM system to be quickly deployed. If you are going to use an external system to connect to iCEFARM, you need to modify some of the configuration in order to make the system discoverable. If you are going to use the same system to run the client, ignore this step. The compose file is located at `docker/compose.yml`. Run `hostname -I` or a similar command to obtain the ip of the system. Then, replace the `services.worker.environment.ICEFARM_VIRTUAL_IP` argument, which is by default set to `localhost`, with the ip of the system - use the raw ip, do not include `http` or a port. In the future, this will not be required.

The system can now be started:
```bash
docker compose -f docker/compose.yml up
```
When you first start the stack, you should see a container named similarly to `db-1` start up (note that the database container uses port 5433 instead of the default to prevent conflicts). Afterwards, a container named similarly to `flyway-1` will start and then exit. Finally, the main iCEFARM `worker-1` and `control-1` containers will start.

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
```bash
python3 -m venv .venv
source .venv/bin/activate
```
Install iCEFARM as a package locally. This allows changes to the package to automatically be applied without having to repackage and install after each modification.
```bash
pip install -e .
```
The package can also be alternatively installed from [pypi](https://pypi.org/project/icefarm/). Run an example that uploads pulse generating circuits to a pulse counting firmware:
```bash
python examples/pulse_count_driver/pulse.py
```
Approximate output:
```
[EventServer] [socket@http://localhost:8080] connected
2 available devices for reservation.
Reserving devices. This may take up to 30 seconds.
[EventServer] [socket@http://localhost:8081] connected
[EventServer] [socket@http://localhost:8081] received initialized event
Received event: initialized serial: 1B66CE91AB184A50 contents: {'event': 'initialized', 'serial': '1B66CE91AB184A50'}
Reserved devices: ['1B66CE91AB184A50']
Expected wait time: 4.20 seconds
Sending bitstreams...
[EventServer] [socket@http://localhost:8081] received results event
Received event: results serial: 1B66CE91AB184A50 contents: {'results': [['9c7c301f-4e20-47d6-a458-f616743663a6', '1998'], ['66b02a50-f731-4413-be1a-9b4c9bad04d6', '7996'], ['d8da0321-5f5e-4dac-afee-ee5905271c8b', '31995']], 'batch_id': 'f37895eb-4426-4175-a11e-827a96200f77', 'event': 'results', 'serial': '1B66CE91AB184A50'}
Serial 1B66CE91AB184A50, bitstream examples/pulse_count_driver/precompiled_circuits/circuit_generated_2Khz.bin, result 1998
Serial 1B66CE91AB184A50, bitstream examples/pulse_count_driver/precompiled_circuits/circuit_generated_8Khz.bin, result 7996
Serial 1B66CE91AB184A50, bitstream examples/pulse_count_driver/precompiled_circuits/circuit_generated_32Khz.bin, result 31995
Total elapsed evaluation time: 5.62
Average circuit evaluation time: 1.87
Total latency: 2.62
Average latency: 0.87
[EventServer] [socket@http://localhost:8081] disconnected: client disconnect
[EventServer] [socket@http://localhost:8080] received reservation end event
```
There will be a small difference in the amount of pulses received between runs. This is because there is a small variance between when the fpga is finished flashing and when the pulse counter starts. The latency represents any time not counting pulses, including flashing (circuits are evaluated for 1 second each). With a small number of circuits the latency is quite high, but with 50 circuits the average latency should be reduced to about 0.24s. This [example](./examples/pulse_count_driver/pulse.py) contains parameters in the script that can be modified.

When a script using iCEFARM exists or is interrupted, devices that have been reserved for usage are automatically made available again. This relies on being able to perform actions after the script has been shutdown. As long as an interrupt is done with SIGINT (`<Ctrl-c>`), this will work normally. However, some things such as the Vscode python debugger's stop button use SIGTERM instead. This immediately terminates the script causing devices to remain reserved. If this happens, you can use the iCEFARM debug panel to manually end device reservations. In addition, reservations are ended automatically after an hour of inactivity.

Stop the stack, this will shutdown the iCEFARM system:
```bash
docker compose -f docker/compose.yml down
```
Note that just using ```ctrl+c``` will not fully shutdown the stack and the database state will persist between runs, which will cause issues.

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
```bash
docker container ls -a
```
These are typically named `docker-worker-1` and `docker-control-1`.
Getting logs:
```bash
docker logs <worker name>
docker logs <control name>
```

#### Device goes to BrokenState
This can happen occasionally even if everything is set up correctly. Restart the stack and plug the device in again. If it happens again, verify that you are able to manually flash firmware on to the device. First, install [picocom](https://github.com/npat-efault/picocom)
Find the device file of the broken device:
```
ls /dev | grep ACM
```
The device should show up with a name similar to `ttyACM0`. If you are using multiple devices, you can use `udevadm info` on each dev file to view their serial id and find the one that matches the problematic one.
Once you find the device, it will enter bootloader mode by connecting with a 1200 baud rate.
```
sudo picocom --baud 1200 /dev/ttyACM0
```
The device will now be mountable as a disk. It should show up with the format `/dev/sd[a-z][1-9]`. Locate the dev file:
```bash
ls /dev | grep sd
```
Create a new folder and mount the disk to it:
```bash
mkdir mount_dir
sudo mount /dev/sda1 mount_dir
```
Copy the `rp2_hello_world` firmware used earlier onto the device. Once the device is unmounted, it will reboot.
```bash
sudo cp [firmware_location] mount_dir
sudo umount mount_dir
```
Confirm that the firmware was uploaded successfully by connecting to the device. Find the dev file and connect to it with picocom:
```bash
ls /dev | grep ACM
sudo picocom /dev/ttyACM0
```
If done correctly, you should see a ```hello world``` message printed repeatedly. You can use `<Ctrl-a>` then `<Ctrl-q>` to exit picocom.

## Client Usage
Create a python venv or use an existing one and install the package:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install icefarm
```

Create a client:
```python
import logging
from icefarm.client.drivers import PulseCountClient
ICEFARM_SERVER = "http://localhost:8080"
CLIENT_NAME = "example icefarm client"

client = PulseCountClient(ICEFARM_SERVER, CLIENT_NAME, logging.getLogger(__name__))
```
If you are running the iCEFARM system through docker compose, the main server defaults to port ```8080```. The client name should be unique across all of the system users. Next, reserve a pico2ice from the system:
```python
client.reserve(1)
```
This sets aside a device for the client to interface with. The device is flashed to firmware specific to the client, in this case one that can upload circuits and count pulses. This method does not return until after the devices are ready to be used, so it may take a few seconds.

During the reservation, this specific device will not be used by other systems. A reservation lasts for an hour; afterwards, the client will no longer be in control of the device. However, the client will automatically extend the duration of reservation to ensure that it does not end during an experiment. While reservations eventually expire on their own, it is good practice manually end reservations when devices are done being used.
```python
import atexit
atexit.register(client.endAll)
```
Note that this will end all reservations under the previously specified client name, so it is important to use a unique name. The client can send instructions to specific devices by using their reported serial id:
```python
serial_id = client.getSerials()[0]
```
The simplest way to evaluate bitstreams is to use the evaluateBitstreams method, but this does not offer much flexibility.
```python
CIRCUITS = ["examples/pulse_count_driver/precompiled_circuits/circuit_generated_2Khz.bin",
            "examples/pulse_count_driver/precompiled_circuits/circuit_generated_8Khz.bin",
            "examples/pulse_count_driver/precompiled_circuits/circuit_generated_32Khz.bin"]

for result in client.evaluateBitstreams(CIRCUITS, serials=[serial_id]):
    print(f"Counted {result.value} pulses from circuit {result.evaluation.filepath} on device {result.serial}!")
```
This sends out the circuits to each of the devices specified. This method produces an iterator that generates results as they are received from the iCEFARM system, so it is most efficient to act on the results as they are iterated on rather than consuming the entire iterator with something like ```list``` . Evaluations done with the client have a small delay as circuits are initially queued into the system, but after startup evaluations are done as fast as they would be locally. It is much faster to send 50 circuits in one evaluation than say 10 batches of 5. The client gradually sends circuits to the system as devices are ready to evaluate them, so sending large evaluations does not cause server stress. The evaluateBitstreams method is convenient, but does all evaluations on the same set of devices. Reserve another device:
```python
client.reserve(1)
serials = client.getSerials()
```
The PulseCountEvaluation class can be used to create more detailed instructions.
```python
from icefarm.client.lib.pulsecount import PulseCountEvaluation

commands = []

# evaluate on both devices
commands.append(PulseCountEvaluation(serials, CIRCUITS[0]))
# evaluate on first device
commands.append(PulseCountEvaluation([serials[0]], CIRCUITS[1]))
# evaluate on second device
commands.append(PulseCountEvaluation([serials[1]], CIRCUITS[2]))
```

Commands can be evaluated in a similar way to using the evaluateBitstreams method. The main difference is rather than returning a filepath in the iterator, the PulseCountEvaluation that created the result is returned.
```python
for result in client.evaluateEvaluations(commands):
    print(f"Counted {result.value} pulses from circuit {result.evaluation.filepath} on device {result.serial}!")
```
The same efficiency guidelines mentioned for evaluateBitstreams apply to evaluateEvaluations. In addition, if you have multiple sets of circuits that need to be evaluated on different devices, it is much faster to use a single evaluateEvaluations than to use multiple evaluateBitstream calls.
Lastly, using multiple threads purely to call evaluate methods multiple times at once will not result in any speedup. This will likely result in slower evaluations as the client will not be able to dispatch commands optimally. See the [website](https://evolvablehardware.github.io/iCEFARM/) or docs folder for additional information about using and developing the client.