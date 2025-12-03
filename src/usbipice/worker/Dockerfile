FROM ubuntu:noble-20240407.1
WORKDIR /usr/local/app

# linux-tools-generic needs to be same version as host kernel
# sudo is installed since its used in subprocess.run
# udev for dev events
RUN apt-get update && apt-get install -y git python3 python3-pip python3-venv linux-tools-6.14.0-36-generic sudo make udev

COPY ./ /usr/local/app/

RUN python3 -m venv .venv
RUN .venv/bin/pip install -e .

# picocom is needed to flash firmware
WORKDIR /usr/local/build
RUN git clone https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make
RUN cp picocom /usr/bin
WORKDIR /usr/local/app

EXPOSE 8080

# docker run --rm -t -i --privileged -v /dev:/dev -v /lib/modules:/lib/modules --network=host -it usbipice bash
# -v /dev:/dev for dev files
# -v /lib/modules:/lib/modules for usbip 

# -v /run/udev:/run/udev:ro to provide additional dev attributes (like ID_SERIAL)
# from https://stackoverflow.com/questions/41753218/udevadm-does-not-show-all-attributes-inside-a-docker-container