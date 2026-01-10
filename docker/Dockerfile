FROM --platform=$BUILDPLATFORM ubuntu:noble-20251013 AS firmware-builder
RUN --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y make cmake gcc-arm-none-eabi linux-tools-generic git python3 build-essential

WORKDIR /usr/local/build
RUN git clone --depth 1 https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make

COPY ./src/icefarm/worker/firmware /usr/local/firmware

WORKDIR /usr/local/firmware
RUN git clone --depth 1 https://github.com/raspberrypi/pico-sdk.git
RUN git clone --depth 1 https://github.com/tinyvision-ai-inc/pico-ice-sdk.git

WORKDIR /usr/local/firmware/pico-sdk
RUN git submodule update --init lib/tinyusb

WORKDIR /usr/local/firmware/pico-ice-sdk
RUN git submodule update --init lib/tinyuf2

WORKDIR /usr/local/firmware/pulse_count/build
RUN cmake -DPICO_BOARD=pico2_ice ..
RUN make

WORKDIR /usr/local/firmware/default/build
RUN cmake -DPICO_BOARD=pico2_ice ..
RUN make


FROM ubuntu:noble-20251013 AS picocom-builder
RUN --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y make cmake gcc-arm-none-eabi linux-tools-generic git python3 build-essential

WORKDIR /usr/local/build
RUN git clone --depth 1 https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make


FROM ubuntu:noble-20251013
WORKDIR /usr/local/app

RUN --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y python3 python3-pip python3-venv sudo udev linux-tools-generic && rm -rf /var/cache/apt/archives /var/lib/apt/lists/*

RUN mkdir -p /run/udev

COPY ./ /usr/local/app/
COPY --from=picocom-builder /usr/local/build/picocom/picocom /usr/bin
# TODO must be a better way
# can't copy entire dir since build artifacts
COPY --from=firmware-builder /usr/local/firmware/default/build/default_firmware.uf2 /usr/local/app/src/icefarm/worker/firmware/default/build/default_firmware.uf2
COPY --from=firmware-builder /usr/local/firmware/pulse_count/build/bitstream_over_usb.uf2 /usr/local/app/src/icefarm/worker/firmware/pulse_count/build/bitstream_over_usb.uf2

WORKDIR /usr/local/app
RUN python3 -m venv .venv
RUN .venv/bin/pip install -e .

EXPOSE 8080