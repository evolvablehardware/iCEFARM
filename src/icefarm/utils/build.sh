yosys -p "synth_ice40 -abc9 -top top -json ${1}/top.json" "${1}/top.v"
nextpnr-ice40 --package sg48 --up5k --freq 48 --top top --pcf $2 --json "${1}/top.json" --asc "${1}/top.asc"
icepack "${1}/top.asc" "${1}/top.bin"