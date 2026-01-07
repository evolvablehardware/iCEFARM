import threading
# TODO once control availability notifications are done,
# wait for those before returning. Currently a test exits immediately,
# so a redundant pico is needed to buffer default firmware flashing

def test_extend_all(client_fac):
    with client_fac() as client:
        assert client.extendAll() == client.getSerials()

def test_extend_serial(client_fac):
    with client_fac() as client:
        serials = client.getSerials()
        assert serials == client.extend(serials)

def test_end_all(client_fac):
    with client_fac() as client:
        client.endAll()
        assert not client.getSerials()

def test_end_serial(client_fac):
    with client_fac() as client:
        serials = client.getSerials()
        client.end(serials)
        assert not client.getSerials()

def test_stack(client_fac):
    with client_fac() as client:
        BITSTREAM_PATHS = ["examples/pulse_count_driver/precompiled_circuits/circuit_generated_2Khz.bin",
                    "examples/pulse_count_driver/precompiled_circuits/circuit_generated_8Khz.bin",
                    "examples/pulse_count_driver/precompiled_circuits/circuit_generated_32Khz.bin"]

        def timeout():
            raise Exception("Watchdog timeout")
        watchdog = threading.Timer(len(BITSTREAM_PATHS) * 20, timeout)
        watchdog.daemon = True
        watchdog.name = "watchdog-timeout"
        watchdog.start()

        pulses = client.evaluateEach(BITSTREAM_PATHS)
        if not pulses:
            raise Exception("Did not receive any pulses")

        assert len(pulses) == 1

        for circuit_map in pulses.values():
            for path in BITSTREAM_PATHS:
                assert path in circuit_map
