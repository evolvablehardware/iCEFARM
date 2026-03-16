# Communication Protocol

The control server contains the following http endpoints:

| Path | Arguments (json) | Description |
|------|------------------|-------------|
| / | None | Web debug panel |
| /available | None | Amount of devices available for reservation. |
| /reserve | amount, name, kind, args | Reserves a device under the client name. The device is initialized using the registered kind and passed args. |
| /devices | None | Serials of devices available for reservation. |
| /reserveserials | serials, name, kind, args | Same as reserve, allows for specific devices to be reserved. |
| /extend | name, serials | Extends the reservation of the specified serials. |
| /extendall | name | Extends the reservation of all devices reserved under the client name.
| /end | name, serials | Ends the reservation of the specified serials. |
| /endall | name | Ends the reservation of all devices reserved under the client name. |
| /reboot | serials | Routes a reboot command for the specified devices to workers. |
| /delete| serials | Routes a delete command for the specified devices to workers. Should only be manually triggered using the web debug panel. |

The control server also accepts websocket connections and informs connected clients of certain events when they take place. This includes updates on reservation statuses and notifications when devices become available for reservation.

While the workers contain http endpoints, these are not called directly by clients:

| Path | Arguments (json) | Description |
|------|------------------|-------------|
| /heartbeat | None | Called periodically. |
| /reserve | serial, kind, args | Initializes a device to be ready to client usage. |
| /reboot | serial | Sends a reboot command to the device state. The device will attempt to recover from a malfunctioning state while preserving client data. |
| /delete | serial | Removes device from internal datastructure. If the device is still connected, the worker will add it back to the system then attempt to flash it to the default firmware. |

The majority of worker communication is done through a websocket.
### Exposing Device States
During a devices reservation, its state determines its behavior and how it can communicate with the client. Device states inherit from ```icefarm.worker.device.state.core.AbstractState``` and can be made available to clients by decorating the class with ```icefarm.worker.device.state.reservable.reservable```. States can receive arguments from the client upon initialization.
```python
@reservable("example state", "message")
class ExampleState(AbstractState):
    def __init__(state, message)
        super().__init__(state)
        print(f"Message from client!: {message}")

```

### Initial Reservation Handshake
When a client is created, it starts a websocket connection to the control server. This allows the control server to send events to the client. Once a client wants to use devices, it uses the ```/reserve``` or ```/reserveserials``` endpoint on the control server. The control server determines which devices the client will be given and figures out what worker servers the devices are located on. In the background, it sends a request to the each relevant worker ```/reserve``` endpoint to initialize the device. When a worker receives a reservation request, it determines which ```AbstractState``` to create using the ```kind``` argument. The ```args``` argument are passed into the ```AbstractState``` during initialization.

The control server then responds with a map of device serials to worker urls.

After the client receives a response from the control server, it creates a websocket connection to each of the provided workers. When a worker is done initializing a device for the client, it sends a ```initialized``` event containing the devices serial through the websocket to the client.

### Handling Client Events
The client uses its ```EventServer``` to receive data from workers and the control server through websockets. This functions like a webserver and has a similar interface to most python web libraries. The client can register methods:
```python
class ExampleEventHandler(AbstractEventHandler):
    @register("results", "data")
    def printResults(self, data)
        print(data)
```
When the ```EventServer``` receives a properly formatted event through a websocket, the method will then be called:
```json
{
    "event": "results",
    "contents": {
        "data": "hello!"
    }
}
```
The control server produces a few different types of events. This includes information about reservations that are expiring soon, and reservations that have ended. The control server also notifies clients when a new device becomes available for reservations. If a device becomes suddenly unexpectedly unavailable, a failure event will be sent.

### Sending Worker Commands
The workers ```AbstractState```s can expose methods to the client. This is done using the ```AbstractState.register``` decorator. Calls are handled through the worker's websocket and file transfers are supported.
```python
class ExampleState(AbstractState):
    ...
    @AbstractState.register("getdata", "data")
    def receiveData(self, data)
        print(f"Got data from client: {data}")
```
When the client wants to invoke the method, it sends the necessary command through the websocket:
```json
{
    "serial": "example pico2ice serial id",
    "event": "getdata",
    "contents": {
        "data": "Hello!"
    }
}
```