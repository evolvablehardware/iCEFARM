# Various firmware
In order to build, the symlinks [pico-sdk](https://github.com/raspberrypi/pico-sdk) and [pico-ice-sdk](https://github.com/tinyvision-ai-inc/pico-ice-sdk) must be first created in this directory. If you have not already, make sure to run ```git submodule update --init``` in the pico-ice-sdk repo.

Commands for convenience:

```
git clone https://github.com/tinyvision-ai-inc/pico-ice-sdk.git
cd pico-ice-sdk
git submodule update --init --recursive


git clone https://github.com/raspberrypi/pico-sdk.git
cd pico-sdk
git submodule update --init --recursive
```

You will want to creating symlinks for the directories such that firmware should have links to the sdks:

```
[..]usbip-ice/src/icefarm/worker/firmware$ ls -la
pico-ice-sdk -> [full_path]/pico-ice-sdk/
pico-sdk -> [full_path]/pico-sdk/
```

Then, run build.sh in this directory.

```
chmod +x build.sh  #if needed
./build.sh
```