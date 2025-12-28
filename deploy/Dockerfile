FROM ubuntu:noble-20251013 AS builder
RUN apt-get update && apt-get install -y make cmake gcc-arm-none-eabi linux-tools-generic git python3 build-essential


WORKDIR /usr/local/build
RUN git clone --depth 1 https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make


COPY ./src/usbipice/worker/firmware /usr/local/firmware
WORKDIR /usr/local/firmware
RUN git clone --depth 1 --recurse-submodules -j8 https://github.com/raspberrypi/pico-sdk.git && git clone --depth 1 --recurse-submodules -j8 https://github.com/tinyvision-ai-inc/pico-ice-sdk.git

WORKDIR /usr/local/firmware/pulse_count/build
RUN cmake -DPICO_BOARD=pico2_ice ..
RUN make

WORKDIR /usr/local/firmware/default/build
RUN cmake -DPICO_BOARD=pico2_ice ..
RUN make


FROM ubuntu:noble-20251013
WORKDIR /usr/local/app

RUN apt-get update && apt-get install -y python3 python3-pip python3-venv sudo udev linux-tools-generic && rm -rf /var/cache/apt/archives /var/lib/apt/lists/*

RUN mkdir -p /run/udev

COPY ./ /usr/local/app/
COPY --from=builder /usr/local/build/picocom/picocom /usr/bin
# TODO must be a better way
# can't copy entire dir since build artifacts
COPY --from=builder /usr/local/firmware/default/build/default_firmware.uf2 /usr/local/app/src/usbipice/worker/firmware/default/build/default_firmware.uf2
COPY --from=builder /usr/local/firmware/pulse_count/build/bitstream_over_usb.uf2 /usr/local/app/src/usbipice/worker/firmware/pulse_count/build/bitstream_over_usb.uf2

WORKDIR /usr/local/app
RUN python3 -m venv .venv

EXPOSE 8080