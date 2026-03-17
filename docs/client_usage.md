## Client Usage
Install the package:
```
pip install icefarm
```

Create a client:
```python
import logging
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