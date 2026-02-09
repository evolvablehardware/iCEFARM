cd default
mkdir build -p
cd build
cmake -DPICO_BOARD=pico2_ice ..
make -j8
cd ../..

cd pulse_count
mkdir build -p
cd build
cmake -DPICO_BOARD=pico2_ice ..
make -j8
cd ../..