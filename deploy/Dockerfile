# NOTE: This image does not contain usbip support.
# If a client reserves a usbip device, this will crash.
FROM ubuntu:noble-20251013
WORKDIR /usr/local/app

RUN apt-get update
RUN apt-get install -y git python3 python3-pip python3-venv
RUN apt-get install -y make cmake gcc-arm-none-eabi
RUN apt-get install -y sudo udev linux-tools-generic

RUN mkdir -p /run/udev

WORKDIR /usr/local/build
RUN git clone https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make
RUN cp picocom /usr/bin

WORKDIR /usr/local/lib
RUN git clone --recurse-submodules -j8 https://github.com/raspberrypi/pico-sdk.git
RUN git clone --recurse-submodules -j8 https://github.com/tinyvision-ai-inc/pico-ice-sdk.git

COPY ./ /usr/local/app/

RUN ln -s /usr/local/lib/pico-sdk /usr/local/app/src/usbipice/worker/firmware/pico-sdk
RUN ln -s /usr/local/lib/pico-ice-sdk /usr/local/app/src/usbipice/worker/firmware/pico-ice-sdk

WORKDIR /usr/local/app/src/usbipice/worker/firmware/pulse_count/build
RUN cmake -DPICO_BOARD=pico2_ice ..
RUN make

WORKDIR /usr/local/app/src/usbipice/worker/firmware/default/build
RUN cmake -DPICO_BOARD=pico2_ice ..
RUN make

WORKDIR /usr/local/app
RUN python3 -m venv .venv
RUN .venv/bin/pip install -e .

RUN apt-get remove -y make cmake gcc-arm-none-eabi
RUN rm -rf /usr/local/lib

EXPOSE 8080