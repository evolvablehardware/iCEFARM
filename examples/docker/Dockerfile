FROM ubuntu:noble-20240407.1
WORKDIR /usr/local/app

# linux-tools-generic needs to be same version as host kernel
# sudo is installed since its used in subprocess.run
RUN apt-get update && apt-get install -y git python3 python3-pip python3-venv linux-tools-6.14.0-36-generic sudo make

RUN python3 -m venv .venv
RUN .venv/bin/pip install git+https://github.com/heiljj/usbip-ice.git

# picocom is needed to flash firmware
WORKDIR /usr/local/build
RUN git clone https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make
RUN cp picocom /usr/bin
WORKDIR /usr/local/app

EXPOSE 8080
