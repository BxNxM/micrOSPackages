"""Shared trigger/echo ultrasonic distance sensor logic."""

try:
    import utime as time
except ImportError:
    import time

from machine import Pin

try:
    from machine import time_pulse_us
except ImportError:
    time_pulse_us = None

from microIO import bind_pin


def sleep_us(delay_us):
    delay_us = int(delay_us)
    if hasattr(time, "sleep_us"):
        time.sleep_us(delay_us)
    else:
        time.sleep(delay_us / 1000000)


def as_bool(value):
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)


def duration_to_mm(duration_us):
    return int(duration_us) * 100 // 582


def duration_to_cm(duration_us):
    return (int(duration_us) / 2) / 29.1


class TriggerEchoSensor:
    def __init__(self, name, trig_pin, echo_pin, trig_logical, echo_logical,
                 timeout_us=40000, trigger_us=10, stabilize_us=2):
        self.name = name
        self.timeout_us = int(timeout_us)
        self.trigger_us = int(trigger_us)
        self.stabilize_us = int(stabilize_us)
        self.trig_pin_no = self._bind_pin(trig_logical, trig_pin)
        self.echo_pin_no = self._bind_pin(echo_logical, echo_pin)
        self.trig_pin = Pin(self.trig_pin_no, mode=Pin.OUT, pull=None)
        self.echo_pin = Pin(self.echo_pin_no, mode=Pin.IN, pull=None)
        self.trig_pin.value(0)

    @staticmethod
    def _bind_pin(logical, pin):
        if pin is None:
            return bind_pin(logical)
        return bind_pin(logical, int(pin))

    def read_duration(self, timeout_us=None):
        if time_pulse_us is None:
            raise RuntimeError("machine.time_pulse_us is not available on this port")
        timeout_us = self.timeout_us if timeout_us is None else int(timeout_us)
        self.trig_pin.value(0)
        sleep_us(self.stabilize_us)
        self.trig_pin.value(1)
        sleep_us(self.trigger_us)
        self.trig_pin.value(0)
        try:
            return time_pulse_us(self.echo_pin, 1, timeout_us)
        except OSError as exc:
            if exc.args and exc.args[0] == 110:
                raise OSError("Out of range")
            raise exc

    def measure_mm(self, timeout_us=None):
        return {"mm": duration_to_mm(self.read_duration(timeout_us=timeout_us))}

    def measure_cm(self, timeout_us=None):
        return {"cm": duration_to_cm(self.read_duration(timeout_us=timeout_us))}

    def _set_trigger_low(self):
        self.trig_pin.value(0)

    def deinit(self):
        self._set_trigger_low()
        self.trig_pin.deinit()
        self.echo_pin.deinit()
