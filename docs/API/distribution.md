# Distribution
When using many picos connected to the same device, computation and io may become strained. The iCEFARM system can use picos distributed across multiple devices.

## With Docker
Using the [compose file](../docker/compose.yml), run everything except the worker container on one device. This device will host the control container as well as the database. Now, the worker container can be run on any amount of devices, including on the one running the control container. When running worker containers, the control and database connection strings will have to be replaced from localhost to that of the control container. In addition, the worker name will have to be replaced with a unique value for each device. Docker swarm cannot be used because it restricts the use of the privileged flag, which is required to access udev events and hotplugged devices.

## With Kubernetes
A [helm repository](https://github.com/evolvablehardware/iCEFARM-helm) is available. The chart deploys a worker to each pod, along with setting up the control container. This is less convenient as it requires kubernetes installations, but it is much easier to update than the non-swarm containers.