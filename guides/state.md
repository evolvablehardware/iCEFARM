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
Called directly after ```\_\_init\_\_```. Used to bypass ```self.switch``` limitation of ```\_\_init\_\_```. Typically not necessary.
**handleAdd/handleRemove**
These are called on udev events specific to the device. This can be useful if the firmware has frequent connections/disconnections, such as when uploading to uf2.
**reboot**
This can be called by the client if the device is misbehaving. This should attempt to restore to an initial state.
**handleExit**
Called when the state object is no longer needed. Returning from this method signals that all resources created by the state have been cleaned up. It is expected that this may take some time. It is also expected that the pico2ice firmware may have changed, but the device state should leave the pico2ice firmware in a condition where it responds to the baud 1200 protocol.

### Exposing state to client reservation
States can be made available to the client by decorating the class with ```icefarm.worker.device.state.reservable``` and providing a name for the state. Additional parameters declare arguments for the client to include during the reservation request. These arguments are provided to the ```\_\_init\_\_``` method when the state is created.
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
Note that the state that includes the main behavior is not actually the one decorated by ```reservable```. The first reservable states job is just to switch to the ```FlashState```. In addition, the ```ExampleStateFlasher``` uses ```start``` rather than ```\_\_init\_\_```, as ```self.switch``` is not supported inside ```\_\_init\_\_```. Once the flashing is complete, the ```FlashState``` consumes ```fac``` and switches to the produced state. The use of lambdas while while switching between states may seem unnecessarily complex. However, deferring the creation of the new state until later is important to providing the guarantee that only one state exists per device.

### Exposing device methods to client
States can make a method remotely available to the client. This is done with the ```AbstractState.register``` decorator (as a classmethod). The first argument provides an identifier for the client to use when calling the method. Subsequent arguments can be provided by the client and are passed into the function. For example, this allows the client to print messages:
```python
@reservable("print")
class PrintState(AbstractState):
    ...

    @AbstractState.register("print message", "message content")
    def print(self, message_content):
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
            "experiment_id": 1234,
            "results": "1234abc",
        })
```
Note that files can also be sent through events. While json serializing a file contents seems awkward, events are sent through websockets so it is still performant. Encoding the files raw bytes to ```cp437``` provides a convenient way to convert them to a string, as it is a strictly 1 byte encoding and uses all permutations.






