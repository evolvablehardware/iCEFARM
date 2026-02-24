FROM ubuntu:noble-20251013
WORKDIR /usr/local/app

RUN --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y python3 python3-pip python3-venv sudo udev linux-tools-generic && rm -rf /var/cache/apt/archives /var/lib/apt/lists/*

RUN mkdir -p /run/udev

COPY ./ /usr/local/app/

WORKDIR /usr/local/app
RUN python3 -m venv .venv
# TODO this should really be another image
RUN .venv/bin/pip install build
RUN .venv/bin/python3 -m build
# wheel name based on version :(
# dash shell string concat
RUN ls dist | grep whl | xargs -I {} .venv/bin/pip3 install "./dist/""{}"