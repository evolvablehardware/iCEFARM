"""
Utility functions that don't fit the other modules.
"""
from __future__ import annotations
from logging import Logger
import re
import subprocess
import os
import inspect
import types
from configparser import ConfigParser
import itertools

from pexpect import fdpexpect

def get_env_default(var, default: str, logger: Logger):
    """Obtains an environment variable. If its not configured, it instead returns
    the default value and logs a warning message."""
    value = os.environ.get(var)

    if not value:
        value = default
        logger.warning(f"{var} not configured, defaulting to {default}")

    return value

def config_else_env(option: str, section: str, parser: ConfigParser, error=True, default=None):
    """Tries to find option from section of a .ini file. If it fails,
    it instead looks at the environment variable option. If this also
    fails, raises exception.."""
    if parser:
        if section in parser.sections():
            value = parser[section].get(option)
            if value:
                return value

    value = os.environ.get(option)
    if error:
        if not value:
            if default:
                return default
            raise Exception(f"Configuration error. Set {section}.{option} in the configuration or specify {option} as an environment variable.")

    return value

def check_default(devpath) -> bool:
    """Checks for whether a device is running the default firmware."""
    # Sometimes closing the fd takes a long time (> 10s) on some firmwares,
    # this might create issues. I'm not really sure what the cause is, I added
    # a read from stdio to the default firmware and it seems to fix the issue.
    # The same behavior happens from opening and closing the file in C.
    try:
        with open(devpath, "r") as f:
            p = fdpexpect.fdspawn(f, timeout=2)
            p.expect("default firmware", timeout=2)

    except Exception:
        return False

    return True

def get_ip() -> str:
    """Obtains local network ip from hostname -I."""
    res = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
    group = re.search("[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+", str(res))
    if group:
        return group.group(0)

def typecheck(fn, args) -> bool:
    """Checks whether args are valid types for fn. Only works on classes
    and non nested list generics. For dict, only checks if arg is a dict."""
    params = inspect.signature(fn).parameters.values()

    if len(params) != len(args):
        return False

    for arg, param in zip(args, params):
        annotation = param.annotation

        if annotation is inspect._empty:
            continue

        if inspect.isclass(annotation):
            if not isinstance(arg, annotation):
                return False

            continue

        if not isinstance(annotation, types.GenericAlias):
            return False

        if annotation.__origin__ is dict:
            continue

        if annotation.__origin__ is not list or not isinstance(arg, list):
            return False

        if len(annotation.__args__) != 1:
            return False

        type_ = annotation.__args__[0]

        for value in arg:
            if not isinstance(value, type_):
                return False

    return True

def json_to_args(json, parameters):
    values = list(map(json.get, parameters))
    if any(map(lambda x : x is None, parameters)):
        return False

    return values

def generate_circuit(hz, build_dir, build_script="src/usbipice/utils/build.sh", pcf_path="src/usbipice/utils/pico_ice.pcf", clk=48000000):
    """Builds a circuit of approximately hz."""
    if not os.path.isdir(build_dir):
        os.mkdir(build_dir)

    incr = int((clk/hz) - 1)
    veri = f"""
    module top (
        input CLK,
        output ICE_27,
        output LED_R,
        output LED_B
    );
    reg [22:0] counter;
    reg out;
    always @(posedge CLK) begin
        counter <= counter + 1;

        if (counter >= {incr}) begin
            out <= 1'b1;
            counter <= 23'b00000000000000000000000;
        end else begin
            out <= 1'b0;
        end
    end

    assign ICE_27 = out;
    assign LED_R = counter[22];
    endmodule
    """

    with open(os.path.join(build_dir, "top.v"), "w") as f:
        f.write(veri)

    subprocess.run(["bash", build_script, build_dir, pcf_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    return os.path.join(build_dir, "top.bin"), clk / incr / 1000

# Ideally would inherit dict but that doesn't behave nicely
class MappedQueues:
    """
    Manages a dict[Any, list[Any]] so that new lists are
    created if a key does not already exist. Empty list values
    mean that the corresponding key is treated as through it does
    not exist.
    """
    def __init__(self):
        self.state = {}

    def __getitem__(self, key) -> list:
        if key not in self.state:
            self.state[key] = []

        return self.state[key]

    def append(self, key, value):
        self[key].append(value)

    def pop(self, key, amount) -> list:
        """Pops up to amount items from queue key. If less
        than amount items are in queue key, all items will
        be popped.."""
        out = []

        for _ in range(amount):
            if key not in self:
                return out

            out.append(self[key].pop())

        return out

    def __bool__(self):
        return any(self.state.values())

    def __contains__(self, value):
        return bool(self.state.get(value))

    def __iter__(self):
        return itertools.takewhile(self.__getitem__, self.state)

    def keys(self):
        return list(iter(self))

    def values(self):
        return [self[key] for key in self]

def batch(l, amount):
    batches = [[] for _ in range(amount)]
    for i, item in enumerate(l):
        batches[i % amount].append(item)

    return batches
