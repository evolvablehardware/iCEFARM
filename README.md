# usbip-ice
Device manager for reserving and interfacing with pico2-ice development boards.

## Architecture Overview
- Control
    - Hosts a database. This keeps track of all of the pico devices, and on-going reservation sessions.
    - Provides an API for reserving devices.
    - Heartbeats workers
- Worker
    - Physically connected to the pico devices.
    - Updates database with devices.
    - Provides APIs for interacting with devices.
- Client
    - Reserve devices using the control API
    - Interface with devices using the worker APIs

### Worker
Each pico maintains a certain state object, which defines the behavior of the device. When clients request for a certain device behavior, such as a pulse-count evaluator, they are indicating which state the pico should switch to. The [reservable](./src/usbipice/worker/device/state/reservable/) module contains the states that the client can request. These states are event based and include hooks for add/remove device events. In addition, a state can make a method available to be called by clients through a web API. This is done in a similar way to how most Python web frameworks declare url paths with decorators and has support for files. States can also send events back to clients.

### Client
The core of the client is the event server. This event server is in change of listening for events sent by device states, and routing them to event handlers.

A separate client interface is made for each device state, and a single device state may have multiple different clients for different situations. The client lib contains a base for each device state, which includes an event handler stub. An example of this is the [pulse count state](./src/usbipice/client/lib/pulsecount.py), which contains an event hook for once the bitstreams have been evaluated. In addition, an API for interacting with methods that the state has made available for web interfacing is included. Continuing with the pulse count example, the client can first use *reserve* to obtain a device, then call *evaluate* to queue a bitstream for evaluation. Once the device state has finished measuring the amount of pulses, it sends a request to the event server of the client. The event server then routes the request into the *results* method on the event handler.

## Deploying
- [Control](./src/usbipice/control/)
- [Workers](./src/usbipice/worker/)

## Usage
- [Client](./src/usbipice/client/)


