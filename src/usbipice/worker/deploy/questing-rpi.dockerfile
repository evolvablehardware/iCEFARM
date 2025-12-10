# TODO must match host image
FROM ubuntu:questing-20251029
WORKDIR /usr/local/app

RUN apt-get update && apt-get install -y git python3 python3-pip python3-venv sudo make udev
# TODO must match host kernel
RUN apt-get install -y linux-tools-6.17.0-1004-raspi 

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
