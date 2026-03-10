# iCE FPGA Array Resource Manager
Device manager for reserving and interfacing with pico2-ice development boards.

## iCEFARM Setup
If you have access to an existing iCEFARM server, you do not need to do this. Setting up iCEFARM is only needed if you want to run locally. Linux is required to run the iCEFARM server (but not for interfacing with the system). It is tested on Ubuntu 24, but most distributions should work fine. Some older Ubuntu versions (<20) will not interact with the picos properly.

The picos need to be prepared by flashing firmware that is tinyusb enabled and being plugged in. The [rp2_hello_world](https://github.com/tinyvision-ai-inc/pico-ice-sdk/tree/main/examples/rp2_hello_world) example from the pico-ice-sdk works for this purpose. Picos can also be plugged into an iCEFARM system once it is already running.

Sometimes other packages can take control of the devices after they are plugged in. Verify that the dev files are present:
```ls /dev | grep ACM```
There should be one `ACM` device per pico when running the `rp2_hello_world` firmware.

Here are known problematic packages may need to be removed:
- brltty
- modemmanager

If the devices still do not show up, examine dmesg output:
```sudo dmesg```

If it is not yet installed, install [Docker Engine](https://docs.docker.com/engine/install/). Follow the [post installation steps](https://docs.docker.com/engine/install/linux-postinstall/) so that you do not need to use sudo. Included below:
```
sudo usermod -aG docker $USERNAME
#new shell or log out and then login
newgrp docker
```

Build the image. You may skip this step and the image will automatically download from [DockerHub](https://hub.docker.com/r/evolvablehardware/icefarm).
```
docker build -f docker/Dockerfile -t evolvablehardware/icefarm:all .
```
A compose file provided, start the stack:
```
docker compose -f docker/compose.yml up
```
This runs:
- iCEFARM control server on port 8080
- iCEFARM worker on port 8081
- Postgres database on port 5433 and applies database migrations

If there is unexpected behavior, check the [troubleshooting](#troubleshooting) section.
Approximate output from worker, assuming one device is plugged in:
```
[DeviceManager] Scanning for devices
[DeviceManager] [{SERIAL}] [FlashState] state is now FlashState
[DeviceManager] [{SERIAL}] [FlashState] sending bootloader signal to /dev/ttyACM0
[DeviceManager] [{SERIAL}] [TestState] state is now TestState
[DeviceManager] [{SERIAL}] [ReadyState] state is now ReadyState
[DeviceManager] Finished scan
```
Note that the order and dev files will vary. In some situations there may be multiple bootloader signals sent. Confirm that the device has been added to the database:
Navigate to the debug dashboard to verify everything is working properly:
```
http://localhost:8080
```
One worker should be shown. Each pico that is plugged in should also appear, with its status displayed as ```available```.
The dashboard includes an overview of the system state, along with some actions. The end reservation action removes a devices reservation. The reboot action sends a reboot signal to the devices state object. In the case of the pulse count state, this means attempting to flash the device with the pulse count firmware and opening a new serial port. The delete action effectively flashes the device to the default firmware. Note that this should only be done if the device is not reserved.

The [pulse count example client](./examples/pulse_count_driver/main.py) can now be run. Verify that iCEFARM is setup properly by installing the client and running the example:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python examples/pulse_count_driver/main.py
```

Stop the stack:
```
docker compose -f docker/compose.yml down
```
Note that just using ```ctrl+c``` will not fully shutdown the stack and the database state will persist between runs, which will create issues.

### Troubleshooting
*Generally, most things by destroying the stack and starting it again*
#### Device goes to BrokenState
This can happen occasionally even if everything is set up correctly. Restart the stack and replug the device in. If it happens again, it's probably a configuration error. Verify that you are able to manually flash firmware on to the device with a baud 1200 compatible firmware:
```
sudo picocom --baud 1200 /dev/ttyACM0
sudo mount /dev/sda1 [mount_location]
sudo cp [firmware_location] [mount_location]
sudo umount [mount_location]
```
Note that you will have to wait between commands for the device to respond, and that the exact device path may be different.

## Client Usage
Install the package:
```
pip install icefarm
```

Create a client:
```python
from logging
from icefarm.client.lib.drivers import PulseCountClient
ICEFARM_SERVER = "http://localhost:8080"
CLIENT_NAME = "example icefarm client"

client = PulseCountClient(ICEFARM_SERVER, CLIENT_NAME, logging.getLogger(__name __))
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
CIRCUITS = ["example1.asc", "example2.asc"]
for serial, filepath, pulses in client.evaluateBitstreams(CIRCUITS, serials=[serial_id]):
    print(f"Counted {pulses} pulses from circuit {filepath} on device {serial}!")
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
commands.append(PulseCountEvaluation(serials, "example1.asc"))
# evaluate on first device
commands.append(PulseCountEvaluation(serials[0], "example2.asc"))
# evaluate on second device
commands.append(PulseCountEvaluation(serials[1], "example3.asc"))
```

Commands can be evaluated in a similar way to using the evaluateBitstreams method. The main difference is rather than returning a filepath in the iterator, the PulseCountEvaluation that created the result is returned.
```python
for serial, evaluation, pulses in client.evaluateEvaluations(commands):
    print(f"Counted {pulses} pulses from circuit {evaluation.filepath} on device {serial}!")
```
The same efficiency guidelines mentioned for evaluateBitstreams apply to evaluateEvaluations. In addition, if you have multiple sets of circuits that need to be evaluated on different devices, it is much faster to use a single evaluateEvaluations than to use multiple evaluateBitstream calls.
Lastly, using multiple threads purely to call evaluate methods multiple times at once will not result in any speedup. This will likely result in slower evaluations as the client will not be able to dispatch commands optimally.
See [examples](./examples/pulse_count_driver/main.py) for an additional example. Note that this is not included in the pip package.


# Fixing a 'Stuck' Worker
Under certain circumstances, there might be an error where a worker on the icefarm needs to be reset. In this case, run the following command if you are running docker container"

```
docker exec docker-db-1 psql -U postgres -p 5433 -c "DELETE FROM worker;"
```