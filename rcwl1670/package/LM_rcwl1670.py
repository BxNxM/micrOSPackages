import time
from machine import Pin
from Types import resolve

_TRIG_PULSE_US = 10
_TIMEOUT_US = 60000  # ~10m max range


class RCWL1670:
    INSTANCE = None

    def __init__(self, trig_pin=16, echo_pin=17):
        self.trig = Pin(trig_pin, Pin.OUT, value=0)
        self.echo = Pin(echo_pin, Pin.IN)

    def measure(self):
        """Trigger measurement and return distance in mm.
        :return int|None: distance in mm, or None on timeout
        """
        self.trig.value(0)
        time.sleep_us(2)
        self.trig.value(1)
        time.sleep_us(_TRIG_PULSE_US)
        self.trig.value(0)

        start = time.ticks_us()
        while self.echo.value() == 0:
            if time.ticks_diff(time.ticks_us(), start) > _TIMEOUT_US:
                return None

        pulse_start = time.ticks_us()
        while self.echo.value() == 1:
            if time.ticks_diff(time.ticks_us(), pulse_start) > _TIMEOUT_US:
                return None

        duration_us = time.ticks_diff(time.ticks_us(), pulse_start)
        # speed of sound: 343 m/s = 0.343 mm/us, round trip -> /2
        return int(duration_us * 0.1715)


def _inst():
    if RCWL1670.INSTANCE is None:
        raise Exception('Not loaded. Call rcwl1670 load first.')
    return RCWL1670.INSTANCE


def load(trig_pin=16, echo_pin=17):
    """Initialize the RCWL-1670 sensor.
    :param trig_pin int: TRIG pin (default: 16)
    :param echo_pin int: ECHO pin (default: 17)
    :return str: status message
    """
    RCWL1670.INSTANCE = RCWL1670(trig_pin, echo_pin)
    return 'RCWL1670 loaded.'


def unload():
    """Release instance.
    :return str: status message
    """
    RCWL1670.INSTANCE = None
    return 'RCWL1670 unloaded.'


def measure():
    """Trigger a single distance measurement.
    :return dict: distance_mm (int) or error (str)
    """
    result = _inst().measure()
    if result is None:
        return {'error': 'timeout'}
    return {'distance_mm': result}


def help(widgets=False):
    """
    [i] micrOS LM naming convention - built-in help message
    :return tuple:
        (widgets=False) list of functions implemented by this application
        (widgets=True) list of widget json for UI generation
    """
    return resolve(('load trig_pin=16 echo_pin=17',
                    'unload',
                    'measure'), widgets=widgets)
