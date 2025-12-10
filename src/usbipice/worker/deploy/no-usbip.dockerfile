# NOTE: This image does not contain usbip support.
# If a client reserves a usbip device, this will crash.
# This image is intended to make testing more convenient, 
# as it does not need to adhere to the usbip requirements.

FROM ubuntu:noble-20240423
WORKDIR /usr/local/app

RUN apt-get update && apt-get install -y git python3 python3-pip python3-venv sudo make udev

COPY ./ /usr/local/app/

RUN mkdir -p /lib/modules
RUN mkdir -p /run/udev

RUN python3 -m venv .venv
RUN .venv/bin/pip install -e .

WORKDIR /usr/local/build
RUN git clone https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make
RUN cp picocom /usr/bin
WORKDIR /usr/local/app

EXPOSE 8080