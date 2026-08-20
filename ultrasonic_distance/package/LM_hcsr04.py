"""
HC-SR04 trigger/echo ultrasonic distance sensor driver for micrOS.
"""

from microIO import pinmap_search
from Types import resolve
from ultrasonic_distance.trigger_echo import (
    TriggerEchoSensor,
    as_bool,
)


SENSOR = None
SENSOR_NAME = "HC-SR04"
DEFAULT_TIMEOUT_US = 1000000
DEFAULT_TRIGGER_US = 10
DEFAULT_STABILIZE_US = 5


def _sensor(trig_pin=None, echo_pin=None, timeout_us=DEFAULT_TIMEOUT_US,
            trigger_us=DEFAULT_TRIGGER_US, stabilize_us=DEFAULT_STABILIZE_US,
            reset=False):
    global SENSOR
    if as_bool(reset) and SENSOR is not None:
        SENSOR.deinit()
        SENSOR = None
    if SENSOR is None:
        SENSOR = TriggerEchoSensor(
            SENSOR_NAME,
            trig_pin=trig_pin,
            echo_pin=echo_pin,
            trig_logical="hcsrtrig",
            echo_logical="hcsrecho",
            timeout_us=timeout_us,
            trigger_us=trigger_us,
            stabilize_us=stabilize_us,
        )
    return SENSOR


def load(trig_pin=None, echo_pin=None, timeout_us=DEFAULT_TIMEOUT_US,
         trigger_us=DEFAULT_TRIGGER_US, reset=False):
    """
    Initialize HC-SR04 ultrasonic distance sensor module.

    Defaults intentionally mirror the core LM_distance module:
    bind_pin("hcsrtrig"), bind_pin("hcsrecho"), 5us stabilize, 10us trigger,
    and 1000000us echo timeout.
    """
    _sensor(trig_pin=trig_pin, echo_pin=echo_pin, timeout_us=timeout_us,
            trigger_us=trigger_us, reset=reset)
    return "HCSR04 Ultrasonic distance sensor - loaded"


def measure_mm():
    """
    Compatibility helper for the core LM_distance API.
    """
    return _sensor().measure_mm()


def measure_cm():
    """
    Compatibility helper for the core LM_distance API.
    """
    return _sensor().measure_cm()


def deinit():
    """
    Deinitialize HC-SR04 pins, matching core LM_distance behavior.
    """
    global SENSOR
    _sensor().deinit()
    SENSOR = None


def pinmap():
    """
    Shows logical pins used by this Load Module.
    """
    return pinmap_search(["hcsrtrig", "hcsrecho"])


def help(widgets=False):
    """
    micrOS LM naming convention - built-in help message.
    """
    return resolve((
        "measure_mm",
        "TEXTBOX{'refresh': 500} measure_cm",
        "deinit",
        "pinmap",
        "load",
        "[info] HCSR04 Ultrasonic distance sensor",
    ), widgets=widgets)
