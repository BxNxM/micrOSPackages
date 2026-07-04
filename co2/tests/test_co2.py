"""Host-side unit tests for the co2 load modules."""

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


PACKAGE_DIR = Path(__file__).resolve().parent.parent / "package"


class FakePin:
    OUT = 1
    PULL_UP = 2

    def __init__(self, pin, *args):
        self.pin = pin
        self._value = 1

    def value(self, value=None):
        if value is not None:
            self._value = value
        return self._value


class FakeUART:
    response = None
    instances = []

    def __init__(self, *args, **kwargs):
        self.writes = []
        self.deinitialized = False
        FakeUART.instances.append(self)

    def init(self, *args, **kwargs):
        self.deinitialized = False

    def any(self):
        return 0

    def read(self, count=None):
        return self.response

    def write(self, data):
        self.writes.append(data)

    def deinit(self):
        self.deinitialized = True


class FakeADC:
    ATTN_11DB = 3
    WIDTH_10BIT = 10
    reading = 512

    def __init__(self, *args):
        pass

    def atten(self, *args):
        pass

    def width(self, *args):
        pass

    def read(self):
        return self.reading


class FakeTaskContext:
    def __init__(self):
        self.out = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    async def feed(self, sleep_ms=0):
        return None


def _micro_task(tag=None, task=None, _wrap=False):
    if task is not None:
        task.close()
        return {"tag": tag, "state": "created"}
    return FakeTaskContext()


def _install_stubs():
    machine = types.ModuleType("machine")
    machine.Pin = FakePin
    machine.UART = FakeUART
    machine.ADC = FakeADC
    sys.modules["machine"] = machine

    micro_io = types.ModuleType("microIO")
    micro_io.bind_pin = lambda name, default=None: default if default is not None else 34
    micro_io.pinmap_search = lambda pins: pins
    sys.modules["microIO"] = micro_io

    common = types.ModuleType("Common")
    common.micro_task = mock.MagicMock(side_effect=_micro_task)
    common.manage_task = mock.MagicMock()
    common.console = mock.MagicMock()
    common.notify = mock.MagicMock(return_value=True)
    sys.modules["Common"] = common

    types_module = types.ModuleType("Types")
    types_module.resolve = lambda values, widgets=False: values
    sys.modules["Types"] = types_module


def _load_module(name):
    spec = importlib.util.spec_from_file_location(
        "{}_under_test".format(name), PACKAGE_DIR / "{}.py".format(name)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_install_stubs()
mhz = _load_module("LM_mh_z19c")
mq135 = _load_module("LM_mq135")


def _mhz_frame(ppm=800, temperature=23, status=0):
    frame = bytearray((0xFF, 0x86, ppm >> 8, ppm & 0xFF,
                       temperature + 40, status, 0, 0, 0))
    frame[8] = mhz.MHZ19._crc8(frame)
    return bytes(frame)


class TestMHZ19(unittest.TestCase):
    def setUp(self):
        FakeUART.instances.clear()
        FakeUART.response = None
        mhz.MHZ19.INSTANCE = None

    def tearDown(self):
        mhz.MHZ19.INSTANCE = None

    def test_measure_parses_valid_frame(self):
        FakeUART.response = _mhz_frame(ppm=1234, temperature=21, status=2)
        self.assertEqual(
            mhz.measure(),
            {"ppm": 1234, "temp": 21, "status": 2},
        )

    def test_measure_rejects_bad_checksum_without_stale_values(self):
        FakeUART.response = b"\xff\x86\x01\x90\x3f\x00\x00\x00\x00"
        sensor = mhz.load()
        sensor.ppm = 999
        result = mhz.measure()
        self.assertIsNone(result["ppm"])
        self.assertIn("error", result)

    def test_measure_rejects_wrong_response_command(self):
        frame = bytearray(_mhz_frame())
        frame[1] = 0x87
        frame[8] = mhz.MHZ19._crc8(frame)
        FakeUART.response = bytes(frame)
        self.assertIn("error", mhz.measure())

    def test_stop_does_not_create_sensor(self):
        self.assertEqual(mhz.stop(), "mh_z19c.sensor: Stopped")
        self.assertEqual(FakeUART.instances, [])

    def test_calibration_restores_pin_and_uart_after_failure(self):
        sensor = mhz.load()

        class FailingTask(FakeTaskContext):
            async def feed(self, sleep_ms=0):
                raise RuntimeError("test failure")

        with mock.patch.object(mhz, "micro_task", return_value=FailingTask()):
            asyncio.run(sensor.calibrate())
        self.assertEqual(sensor.hd_pin.value(), 1)
        self.assertFalse(sensor.uart.deinitialized)


class TestMQ135(unittest.TestCase):
    def setUp(self):
        FakeADC.reading = 512
        mq135.__dict__["__ADC"] = None
        mq135.__dict__["__ADC_PROP"] = (1023, 1.0)

    def test_corrected_measurement_returns_ppm_and_verdict(self):
        result = mq135.measure_mq135(temperature=23, humidity=45)
        ppm_text, verdict = result.split(" - ")
        self.assertGreater(float(ppm_text), 0)
        self.assertIn(verdict, {"PERFECT", "POOR", "WARNING", "CRITICAL"})

    def test_missing_compensation_is_reported(self):
        self.assertIn("Missing mandatory parameters", mq135.measure_mq135())

    def test_zero_adc_reading_is_reported(self):
        FakeADC.reading = 0
        self.assertIn("invalid ADC reading", mq135.measure_mq135(23, 45))
        self.assertIn("invalid ADC reading", mq135.raw_measure_mq135())

    def test_saturated_adc_reading_is_reported(self):
        FakeADC.reading = 1023
        self.assertIn("invalid ADC reading", mq135.measure_mq135(23, 45))

    def test_help_uses_public_parameter_names(self):
        self.assertIn(
            "TEXTBOX measure_mq135 temperature=None humidity=None",
            mq135.help(),
        )


if __name__ == "__main__":
    unittest.main()
