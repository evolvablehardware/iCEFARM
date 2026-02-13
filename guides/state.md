# Device State Information
- What is a device state?
- Creating new device states
- Interfacing with new device states
- Receiving information from devices

## What is a device state?
Each physical pico2ice has a separate device state. The state defines how the device behaves. It also defines the possible interactions between the device and the client. When a client specifies the type of behavior a reserved device should have, the device is set to a corresponding state. Each device state inherits from [```icefarm.worker.device.state.core.AbstractState```](../src/icefarm/worker/device/state/core/AbstractState.py). Device states that are made available for client reservation are located in the [```icefarm.worker.device.state.reservable```](../src/icefarm/worker/device/state/reservable/) module.

## Creating new device states
### Useful AbstractState attributes
**device_event_sender**
A ```icefarm.worker.device.DeviceEventSender```. Allows information to be sent to the client.
**serial**
Serial id of the device.
**switch()**
Switches to a different device state.
**

### Methods
**\_\_init\_\_**
When the state is requested by the client, the state is initialized. This is expected to return after a few seconds. If a background task is required, this should be done by creating a separate thread. Note that ```self.switch``` cannot be called here as a result of the guarantee that only one state exists at a time. When the device is ready to be used by the client, this is done with ```self.device_event_sender.sendDeviceInitialized``` (this does not strictly have to be done here, but is often the case).
**start**
Called directly after ```__init__```. Used to bypass ```self.switch``` limitation of ```__init__```. Typically not necessary.
**handleAdd/handleRemove**
These are called on udev events specific to the device. This can be useful if the firmware has frequent connections/disconnections, such as when uploading to uf2.
**reboot**
This can be called by the client if the device is misbehaving. This should attempt to restore to an initial state.
**handleExit**
Called when the state object is no longer needed. Returning from this method signals that all resources created by the state have been cleaned up. It is expected that this may take some time. It is also expected that the pico2ice firmware may have changed, but the device state should leave the pico2ice firmware in a condition where it responds to the baud 1200 protocol.

### Exposing state to client reservation
States can be made available to the client by decorating the class with ```icefarm.worker.device.state.reservable``` and providing a name for the state. Additional parameters declare arguments for the client to include during the reservation request. These arguments are provided to the ```__init__``` method when the state is created.
```python
@reservable("example")
class ExampleState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.device_event_sender.sendDeviceInitialized()
```

### Flashing firmware
Firmware flashing can be done by switching to the a ```icefarm.worker.device.state.core.FlashState``` state. Flashing directly after initialization can be done with the following pattern:
```python
FIRMWARE_PATH = ...
class ExampleState(AbstractState):
    ...

@reservable("example")
class ExampleStateFlasher(AbstractState):
    def start(self):
        fac = lambda : ExampleState(self.device)
        self.switch(lambda : FlashState(self.device, FIRMWARE_PATH, fac))
```
Note that the state that includes the main behavior is not actually the one decorated by ```reservable```. The first reservable states job is just to switch to the ```FlashState```. In addition, the ```ExampleStateFlasher``` uses ```start``` rather than ```__init__```, as ```self.switch``` is not supported inside ```__init__```. Once the flashing is complete, the ```FlashState``` consumes ```fac``` and switches to the produced state. The use of lambdas while while switching between states may seem unnecessarily complex. However, deferring the creation of the new state until later is important to providing the guarantee that only one state exists per device.

### Exposing device methods to client
States can make a method remotely available to the client. This is done with the ```AbstractState.register``` decorator (as a classmethod). The first argument provides an identifier for the client to use when calling the method. Subsequent arguments can be provided by the client and are passed into the function. For example, this allows the client to print messages:
```python
@reservable("print")
class PrintState(AbstractState):
    ...

    @AbstractState.register("print message", "message content")
    # Arguments are type checked before being passed in. Only classes and non nested list
    # generics are supported currently.
    def print(self, message_content: str):
        print(message_content)

```
The common use case for this is to add jobs to a queue while a separate thread executes them.

### Sending events to client
Messages can be sent using the ```self.device_event_sender``` ```DeviceEventSender``` instance. Messages must be json serializable. Note that the *event* key is replaced in the message, do not use it.
```python
@reservable("example")
class ExampleState(AbstractState):
    def __init__(state):
        super().__init__(state)
        self.device_event_sender.sendDeviceInitialized("experiment results", {
            "experiment_id": 1234
            "results": "1234abc",
        })
```
Note that files can also be sent through events. While json serializing a file contents seems awkward, events are sent through websockets so it is still performant. Encoding the files raw bytes to ```cp437``` provides a convenient way to convert them to a string, as it is a strictly 1 byte encoding and uses all permutations.

### Design guidelines
States should be written with the assumption that anything that can go wrong will go wrong; A lot can happen during a long experiment.

Typically states will want to have a separate thread that processes hardware intensive tasks rather than handling it directly in the method exposed to the client. When the method exposed to the client is called, it should simply add the task to a queue for the thread to use. This allows the client to send multiple requests to the device state at once. Once the first task is evaluated, the next one can be started without having to wait for communication overhead.

Data sent back to the client should be unprocessed within reason. For example, the pulse count state sends the raw amount of pulses back to the client rather than a fitness. This allows the fitness calculation to be changed in BitstreamEvolution without modifying iCEFARM.

When sending experiment data back to the client, it is best to send multiple results in small batches to reduce communication overhead. The ability to send batch requests to ```AbstractState.register``` decorated methods is derived automatically, so there is no need to implement batch client requests.

## Interfacing with device states
### Configuring reservation type
Communication is done through the ```icefarm.worker.lib.BaseClient``` class. While all desired behavior can be achieved from the base class, it is best to subclass it in two stages. The first subclass only contains functionality required to reserve and communicate with the device state, while the second contains use case specific functionality. The base class should be placed in ```icefarm.client.lib```. The ```reserve``` and ```reserveSpecific``` methods should be configured to automatically reserve the specific device state - this is done by specifying the id passed to the device states ```reservable``` decorator. If applicable, arguments passed to the device state upon initialization should be nicely exposed as function parameters.
*icefarm/client/lib/example.py*
```python
class ExampleBaseClient(BaseClient):
    def reserve(self, amount: int):
        args = {}
        return super().reserve(amount, "example", args)

    def reserveSpecific(self, serials: list[str]):
        args = {}
        return super().reserveSpecific(serials, "example", args)

```
### Calling registered methods
Devices can be sent information using ```BaseClient.requestWorker``` and ```BaseClient.requestBatchWorker```. The later is more efficient and will be covered in the next section. The ```event``` argument corresponds with the ```AbstractState.register``` decorated id. For example, the ```PrintState.print``` method described earlier would use ```print message``` as the event. If the decorator contains additional arguments, these are used as keys to the ```data``` parameter and passed into the method. For ```PrintState.print```, this would be the ```message content``` key.
*icefarm/client/lib/printc.py*
```python
class PrintBaseClient(BaseClient)
    ...

    def print(self, serial: str, message: str):
        args = {"message content": message}
        return super().requestWorker(self, serial, "print message", args)
```

### Efficiently using multiple pico2ices
Often it is desired to send the same request to multiple devices. Since multiple devices can be located on the same worker, using ```BaseClient.requestWorker``` can create unnecessary overhead. The ```BaseClient.requestBatchWorker``` addresses this issue. This allows multiple devices to be sent the same request at once. For devices that are located on the same worker, the contents of the request are only sent over once.

*icefarm/client/lib/printc.py*
```python
class PrintBaseClient(BaseClient):
    ...

    def printBatch(self, serials: list[str], message: str):
        args = {"message content": message}
        return super().requestBatchWorker(self, serials, "print message", args)
```

### Receiving data
The ```client.lib.AbstractEventHandler``` can be used to handle incoming data (```client.lib.utils``` contains some general event handlers). Event handlers can register methods to be called when a particular event is sent to the client. Consider the [earlier](#sending-events-to-client) example with the ```experiment results``` event identifier and following json structure:
```json
{
    "experiment_id": 1234,
    "results": "1234abc"
}
```
Eventhandlers are passed results in an similar way to how the registered device state methods work, except the first argument given is implicitly the device serial that sent the event (and they are not typechecked). This one would print the results it receives:
*icefarm/client/lib/example.py*
```python
from icefarm.client.lib import AbstractEventHandler, register
class ExperimentHandler(AbstractEventHandler):
    # super().__init__:
    # def __init__(self, event_server: EventServer):
    #     self.event_server = event_server

    # first argument is event specified
    @register("experiment results", "experiment_id", "results")
    def printResult(self, serial, experiment_id, results):
        print(f"Got result from {serial} for experiment {experiment_id}: {results}")
```

### Integrating event handlers into client
Event handlers are added in the second ```BaseClient``` subclass. They can be added using ```BaseClient.addEventHandler```. There are also additional event handlers available in ```icefarm.client.lib.utils```.
```python
class PrintClient(PrintBaseClient):
    def __init__(self, url, client_name, logger)
        super().__init__(url, client_name, logger)
        eh = ExperimentHandler(self.server)
        self.addEventHandler(eh)
```

### Batching experiment requests
# TODO going to make this simpler to implement
This assumes that the device state has the ability to queue experiment requests as described in the design [guidelines](#design-guidelines). In addition, the evaluation method needs to take an identifier that is sent back with the experiment results.

When sending experiment evaluations, it is ideal that the experiment queue is always populated, as this reduces downtime. However, we also don't want to send everything at once, as this may overwhelm the system. The solution to is to monitor the amount of evaluations left in the queue by counting the number of results received by the client, and only sending new evaluations when the queue is nearing empty. The ```icefarm.client.lib.BatchRequest``` module provides tools to implement this.

Each evaluation to be sent to to the system is represented by an ```Evaluation``` class. By default, this only contains a list of serials, but it is intended to be subclasses to add additional information such as a circuit filepath or evaluation duration. Note that the ```Evaluation``` may contain multiple serials - it is more efficient to use an ```Evaluation``` with multiple serials than multiple evaluations if possible, as the ```BaseClient.sendBatchWorker``` method can be used.

Once the ```Evaluation```s have been created, they can be put into an ```EvaluationBundle```. This can generate efficient batches of ```Evaluation```s to be sent off to workers. Lastly, the bundle can be placed into a ```BalancedBatchFactory```. The batch factory requires the client to call ```BalancedBatchFactory.processResult``` as results are sent back to the client. In return, the ```BalancedBatchFactory.getBatches``` generator will only return items when the workers are ready to receive a new batch.
