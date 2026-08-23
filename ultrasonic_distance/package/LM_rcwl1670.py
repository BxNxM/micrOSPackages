"""
RCWL-1670 trigger/echo ultrasonic distance sensor driver for micrOS.
"""

from microIO import pinmap_search
from Types import resolve
from ultrasonic_distance.trigger_echo import (
    TriggerEchoSensor,
    as_bool,
)


SENSOR = None


def _sensor(trig_pin=32, echo_pin=35, timeout_us=40000, trigger_us=10, reset=False):
    global SENSOR
    if as_bool(reset) and SENSOR is not None:
        SENSOR.deinit()
        SENSOR = None
    if SENSOR is None:
        SENSOR = TriggerEchoSensor(
            "RCWL-1670",
            trig_pin=trig_pin,
            echo_pin=echo_pin,
            trig_logical="dist_trig",
            echo_logical="dist_echo",
            timeout_us=timeout_us,
            trigger_us=trigger_us,
            stabilize_us=2,
        )
    return SENSOR


def load(trig_pin=32, echo_pin=35, timeout_us=40000, trigger_us=10, reset=False):
    """
    Create and cache the RCWL-1670 trigger/echo sensor.

    :param trig_pin int: MCU output connected to RX/TRIG, default: 32
    :param echo_pin int: MCU input connected to TX/ECHO, default: 35
    :param timeout_us int: echo pulse timeout in microseconds, default: 40000
    :param trigger_us int: trigger pulse length in microseconds, default: 10
    :param reset bool: recreate cached sensor instance
    """
    _sensor(
        trig_pin=trig_pin,
        echo_pin=echo_pin,
        timeout_us=timeout_us,
        trigger_us=trigger_us,
        reset=reset,
    )
    return "RCWL-1670 Ultrasonic distance sensor - loaded"


def measure_mm():
    """
    Measure distance in millimeters.
    """
    return _sensor().measure_mm()


def measure_cm():
    """
    Measure distance in centimeters.
    """
    return _sensor().measure_cm()


def deinit():
    """
    Deinitialize RCWL-1670 pins.
    """
    global SENSOR
    if SENSOR is not None:
        SENSOR.deinit()
        SENSOR = None


def pinmap():
    """
    Shows logical pins used by this Load Module.
    """
    return pinmap_search(["dist_trig", "dist_echo"])


def help(widgets=False):
    """
    micrOS LM naming convention - built-in help message.
    """
    return resolve((
        "load trig_pin=32 echo_pin=35 timeout_us=40000",
        "measure_mm",
        "TEXTBOX{'refresh': 500} measure_cm",
        "deinit",
        "pinmap",
    ), widgets=widgets)
