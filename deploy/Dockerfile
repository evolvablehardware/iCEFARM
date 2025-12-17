# NOTE: This image does not contain usbip support.
# If a client reserves a usbip device, this will crash.
FROM ubuntu:noble-20240423
WORKDIR /usr/local/app

RUN apt-get update && apt-get install -y git python3 python3-pip python3-venv sudo make udev
RUN apt-get install -y linux-tools-6.14.0-36-generic

RUN mkdir -p /run/udev

WORKDIR /usr/local/build
RUN git clone https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make
RUN cp picocom /usr/bin
WORKDIR /usr/local/app

COPY ./ /usr/local/app/

RUN python3 -m venv .venv
RUN .venv/bin/pip install -e .

EXPOSE 8080