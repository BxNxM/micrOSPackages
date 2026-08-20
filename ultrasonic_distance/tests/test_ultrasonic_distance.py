"""Host-side unit tests for the ultrasonic_distance package load modules."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


PACKAGE_DIR = Path(__file__).resolve().parent.parent / "package"


class FakePin:
    OUT = 1
    IN = 0

    def __init__(self, pin, *args, **kwargs):
        self.pin = pin
        self.args = args
        self.kwargs = kwargs
        self.values = []
        self._value = 0
        self.deinitialized = False

    def value(self, value=None):
        if value is not None:
            self._value = value
            self.values.append(value)
        return self._value

    def deinit(self):
        self.deinitialized = True


class FakePulse:
    duration_us = 1000
    durations = []
    calls = []

    @classmethod
    def time_pulse_us(cls, pin, level, timeout_us):
        cls.calls.append((pin.pin, level, timeout_us))
        if cls.durations:
            return cls.durations.pop(0)
        return cls.duration_us


def _install_stubs():
    machine = types.ModuleType("machine")
    machine.Pin = FakePin
    machine.time_pulse_us = FakePulse.time_pulse_us
    sys.modules["machine"] = machine

    micro_io = types.ModuleType("microIO")
    pin_defaults = {
        "hcsrtrig": 32,
        "hcsrecho": 35,
        "rcwl1670_trig": 16,
        "rcwl1670_echo": 17,
    }
    micro_io.bind_pin = lambda name, default=None: pin_defaults[name] if default is None else default
    micro_io.pinmap_search = lambda pins: pins
    sys.modules["microIO"] = micro_io

    common = types.ModuleType("Common")
    common.console = mock.MagicMock()
    sys.modules["Common"] = common

    types_module = types.ModuleType("Types")
    types_module.resolve = lambda values, widgets=False: values
    sys.modules["Types"] = types_module

    distance_pkg = types.ModuleType("ultrasonic_distance")
    distance_pkg.__path__ = [str(PACKAGE_DIR)]
    sys.modules["ultrasonic_distance"] = distance_pkg


def _load_module(name):
    spec = importlib.util.spec_from_file_location(
        "{}_under_test".format(name), PACKAGE_DIR / "{}.py".format(name)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_install_stubs()
hcsr04 = _load_module("LM_hcsr04")
rcwl1670 = _load_module("LM_rcwl1670")


class TestUltrasonicDistancePackage(unittest.TestCase):
    def setUp(self):
        FakePulse.duration_us = 1000
        FakePulse.durations = []
        FakePulse.calls.clear()
        hcsr04.SENSOR = None
        rcwl1670.SENSOR = None

    def tearDown(self):
        hcsr04.SENSOR = None
        rcwl1670.SENSOR = None

    def test_modules_share_trigger_echo_sensor_logic(self):
        self.assertIs(hcsr04.TriggerEchoSensor, rcwl1670.TriggerEchoSensor)

    def test_rcwl1670_measure_mm_uses_trigger_echo_pulse_mode(self):
        self.assertEqual(rcwl1670.measure_mm(), {"mm": 1000 * 100 // 582})
        self.assertEqual(FakePulse.calls, [(17, 1, 40000)])

    def test_hcsr04_matches_core_measurement_helpers(self):
        self.assertEqual(hcsr04.load(), "HCSR04 Ultrasonic distance sensor - loaded")
        self.assertEqual(hcsr04.measure_mm(), {"mm": 1000 * 100 // 582})
        self.assertEqual(hcsr04.measure_cm(), {"cm": (1000 / 2) / 29.1})
        self.assertEqual(FakePulse.calls, [(35, 1, 1000000), (35, 1, 1000000)])

    def test_rcwl1670_has_matching_measurement_helpers(self):
        self.assertEqual(rcwl1670.load(), "RCWL-1670 Ultrasonic distance sensor - loaded")
        self.assertEqual(rcwl1670.measure_mm(), {"mm": 1000 * 100 // 582})
        self.assertEqual(rcwl1670.measure_cm(), {"cm": (1000 / 2) / 29.1})
        self.assertEqual(FakePulse.calls, [(17, 1, 40000), (17, 1, 40000)])

    def test_hcsr04_uses_core_default_pin_bindings(self):
        hcsr04.load()
        self.assertEqual(hcsr04.SENSOR.trig_pin_no, 32)
        self.assertEqual(hcsr04.SENSOR.echo_pin_no, 35)
        self.assertEqual(hcsr04.SENSOR.timeout_us, 1000000)
        self.assertEqual(hcsr04.SENSOR.stabilize_us, 5)

    def test_measure_timeout_raises_like_core_module(self):
        FakePulse.duration_us = -2
        self.assertEqual(rcwl1670.measure_mm(), {"mm": -1})

    def test_deinit_clears_instance(self):
        rcwl1670.load()
        rcwl1670.deinit()
        self.assertIsNone(rcwl1670.SENSOR)

    def test_help_and_pinmap_list_sensor_specific_names(self):
        self.assertEqual(
            rcwl1670.help(),
            (
                "load trig_pin=16 echo_pin=17 timeout_us=40000",
                "measure_mm",
                "TEXTBOX measure_cm",
                "deinit",
                "pinmap",
            ),
        )
        self.assertEqual(
            hcsr04.help(),
            (
                "measure_mm",
                "TEXTBOX measure_cm",
                "deinit",
                "pinmap",
                "load",
                "[info] HCSR04 Ultrasonic distance sensor",
            ),
        )
        self.assertEqual(rcwl1670.pinmap(), ["rcwl1670_trig", "rcwl1670_echo"])
        self.assertEqual(hcsr04.pinmap(), ["hcsrtrig", "hcsrecho"])


if __name__ == "__main__":
    unittest.main()
