import threading
import sys
# TODO once control availability notifications are done,
# wait for those before returning. Currently a test exits immediately,
# so a redundant pico is needed to buffer default firmware flashing

def test_pulse_extend_all(get_pulse):
    with get_pulse() as client:
        assert client.extendAll() == client.getSerials()

def test_pulse_extend_serial(get_pulse):
    with get_pulse() as client:
        serials = client.getSerials()
        assert serials == client.extend(serials)

def test_pulse_end_all(get_pulse):
    with get_pulse() as client:
        client.endAll()
        assert not client.getSerials()

def test_pulse_end_serial(get_pulse):
    with get_pulse() as client:
        serials = client.getSerials()
        client.end(serials)
        assert not client.getSerials()

def test_pulse_evaluate_bitstreams(get_pulse):
    with get_pulse() as client:
        BITSTREAM_PATHS = ["examples/pulse_count_driver/precompiled_circuits/circuit_generated_2Khz.bin",
                    "examples/pulse_count_driver/precompiled_circuits/circuit_generated_8Khz.bin",
                    "examples/pulse_count_driver/precompiled_circuits/circuit_generated_32Khz.bin"]

        def timeout():
            sys.exit("Watchdog timeout")

        watchdog = threading.Timer(len(BITSTREAM_PATHS) * 60, timeout)
        watchdog.daemon = True
        watchdog.name = "watchdog-timeout"
        watchdog.start()

        pulses = list(client.evaluateBitstreams(BITSTREAM_PATHS))

        assert len(pulses) ==  3
        assert set(BITSTREAM_PATHS) == set(item[1] for item in pulses)

def test_varmax_extend_all(get_varmax):
    with get_varmax() as client:
        assert client.extendAll() == client.getSerials()

def test_varmax_extend_serial(get_varmax):
    with get_varmax() as client:
        serials = client.getSerials()
        assert serials == client.extend(serials)

def test_varmax_end_all(get_varmax):
    with get_varmax() as client:
        client.endAll()
        assert not client.getSerials()

def test_varmax_end_serial(get_varmax):
    with get_varmax() as client:
        serials = client.getSerials()
        client.end(serials)
        assert not client.getSerials()

def test_varmax_evaluate_bitstreams(get_varmax):
    with get_varmax() as client:
        BITSTREAM_PATHS = ["examples/pulse_count_driver/precompiled_circuits/circuit_generated_2Khz.bin",
                    "examples/pulse_count_driver/precompiled_circuits/circuit_generated_8Khz.bin",
                    "examples/pulse_count_driver/precompiled_circuits/circuit_generated_32Khz.bin"]

        def timeout():
            sys.exit("Watchdog timeout")

        watchdog = threading.Timer(len(BITSTREAM_PATHS) * 60, timeout)
        watchdog.daemon = True
        watchdog.name = "watchdog-timeout"
        watchdog.start()

        pulses = list(client.evaluateBitstreams(BITSTREAM_PATHS))

        assert len(pulses) ==  3
        assert set(BITSTREAM_PATHS) == set(item[1] for item in pulses)