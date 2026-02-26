# Variance Maximization — Testing Plan

## Overview
This document describes how to test the variance maximization fitness function
end-to-end through the iCEFARM system with pico2-ice hardware.

---

## 1. Unit Tests — Worker-Side Variance Calculation

**File**: `iCEFARM/src/icefarm/worker/device/state/reservable/VarMaxState.py`

Test `calculate_variance()` directly:

```python
from icefarm.worker.device.state.reservable.VarMaxState import calculate_variance

# Constant signal → zero variance
assert calculate_variance([100, 100, 100, 100, 100]) == 0.0

# Known signal: [0, 100, 0, 100, 0]
# Differences: |100|, |100|, |100|, |100| = 400
# 400 / 5 = 80.0
assert calculate_variance([0, 100, 0, 100, 0]) == 80.0

# Single sample → zero
assert calculate_variance([42]) == 0.0

# Empty → zero
assert calculate_variance([]) == 0.0

# Ascending: [0, 1, 2, 3, 4]
# Differences: 1+1+1+1 = 4, 4/5 = 0.8
assert calculate_variance([0, 1, 2, 3, 4]) == 0.8
```

---

## 2. Unit Tests — VarMaxReader Serial Parsing

**What to test**: The `VarMaxReader` parses firmware serial output correctly.

Test with mock serial port data:
- `"samples: 512,489,523,501,498\r\n"` → parsed as `[512, 489, 523, 501, 498]`
- `"Watchdog timeout\r\n"` → returns `False`
- `"Waiting for bitstream transfer\r\n"` → sets `ready = True`

---

## 3. Firmware Build Verification

### Local Build (requires pico-sdk + pico-ice-sdk)
```bash
cd iCEFARM/firmware
# Ensure SDKs are present (clone or symlink)
./build.sh
# Verify output:
ls -la variance/build/variance_firmware.uf2
```

### Docker Build
```bash
cd iCEFARM
docker compose -f docker/compose.yml build
# Verify the firmware is in the image:
docker run --rm evolvablehardware/icefarm:all \
  ls -la src/icefarm/worker/firmware/variance/build/variance_firmware.uf2
```

---

## 4. Worker Registration Check

Start iCEFARM and verify "variance" appears in registered reservables:

```bash
cd iCEFARM
# Clear stale workers first
docker exec docker-db-1 psql -U postgres -p 5433 -c "DELETE FROM worker;"

# Restart
docker compose -f docker/compose.yml restart worker

# Check worker registered with variance capability
docker exec docker-db-1 psql -U postgres -p 5433 -c \
  "SELECT id, reservables FROM worker;"
```

Expected output should include `{pulsecount,variance}` in the reservables array.

---

## 5. Hardware Integration Test (with pico2-ice)

**Prerequisites**:
- pico2-ice board connected via USB
- FPGA output routed to ICE_26 (connected to GPIO 26 / ADC0)

### Manual test:
1. Start iCEFARM: `docker compose -f docker/compose.yml up`
2. Verify worker starts and devices appear at `http://localhost:8080`
3. Reserve a device as "variance" type:
   ```bash
   curl "http://localhost:8080/reserve?amount=1&kind=variance&client_id=test"
   ```
4. Check that the device transitions to VarMaxState (worker logs should show "Sampling ADC")

---

## 6. End-to-End Test with BitstreamEvolution

### Config (`farmconfig.ini`):
```ini
[TOP-LEVEL PARAMETERS]
SIMULATION_MODE = REMOTE
BASE_CONFIG = data/default_config.ini

[FITNESS PARAMETERS]
FITNESS_FUNC = VARIANCE

[ICEFARM PARAMETERS]
MODE = all
DEVICES = 1
URL = http://localhost:8080

[STOPPING CONDITION PARAMETERS]
GENERATIONS = 5
```

### Run:
```bash
cd BitstreamEvolutionPico2ice
docker run -it --network=host \
  -v ./workspace:/usr/local/app/workspace \
  -v ./farmconfig.ini:/usr/local/app/farmconfig.ini \
  bitstreamevolution \
  .venv/bin/python3 src/evolve.py -c farmconfig.ini -d "variance test"
```

### Expected behavior:
1. Client connects to control server at :8080
2. Reserves 1 device as "variance" kind
3. Device flashes variance firmware (.uf2)
4. For each generation:
   - Circuits compiled to .bin bitstreams
   - Bitstreams sent to worker via socket
   - Worker flashes FPGA, samples ADC (500 samples at 10kHz)
   - Worker calculates variance fitness, sends result back
   - Client receives float variance fitness per circuit
5. Evolution progresses with variance-based fitness

### What to look for in logs:
- **Worker**: `"queued bitstreams"`, `"waiting for ADC samples"`, `"got variance fitness: X.XX from 500 samples"`
- **Client**: `"Sending circuits for remote evaluation..."`, `"Remote evaluation complete."`
- **Control**: Device status transitions: available → reserved → initialized

---

## 7. Known Limitations / Edge Cases

1. **No variance firmware path set**: If `USBIPICE_VARIANCE` is not configured, `Config.variance_firmware_path` will be `None`. Attempting to reserve as "variance" will fail at flash time. The worker should transition to BrokenState.

2. **FPGA output not connected to ADC pin**: If the FPGA design doesn't route output to ICE_26, ADC readings will be noise/zero. The variance fitness will reflect this (near-zero for constant, random for noise).

3. **Backward compatibility**: All changes are additive. Existing pulse count functionality is unchanged. The `kind` parameter defaults to `"pulsecount"`.

4. **Firmware sample output buffer**: The firmware flushes USB CDC every 10 samples to avoid buffer overflow. For 500 samples, this is ~50 flushes. If USB is slow, the total output time could be significant (~50-100ms).
