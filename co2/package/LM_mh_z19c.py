"""
MH-Z19 CO2 sensor driver for MicroPython (supports MH-Z19B and MH-Z19C).

Provides a simple interface to read:
    - Co2 concentration (PPM)
    - Temperature
    - Status

Calibration (MH-Z19C)
---------------------
There are two ways to calibrate the zero point on MH-Z19C:

1) Apply a low-level signal for more than 7 seconds.

2) Send the calibration command:
   FF 01 87 00 00 00 00 00 78
   On success the sensor returns:
   FF 87 01 00 00 00 00 00 78

Auto-calibration (ABC) period
-----------------------------
Set 7-day automatic calibration period:
    Command:      FF 01 AF 01 07 00 00 00 48
    Confirmation: FF AF 01 07 00 00 00 00 49

Set 1-day automatic calibration period:
    Command:      FF 01 AF 01 01 00 00 00 4E
    Confirmation: FF AF 01 01 00 00 00 00 4F

Notes
-----
- Use a well-ventilated environment (around 400 ppm) for command-based zero calibration

:author: Florian Mandl
:version: 1.0
:date: 2026-07-04
"""

import time
import json
from machine import Pin, UART
from microIO import bind_pin, pinmap_search
from Common import micro_task, manage_task, console, notify
from Types import resolve


class MHZ19:
    INSTANCE = None

    SENSOR_TASK = 'mh_z19c.sensor'
    CALIBRATE_TASK = 'mh_z19c.calibrate'

    def __init__(self, tx_pin=16, rx_pin=17, hd_pin=19):
        self.uart_no = 1
        self.ppm = 0
        self.temp = 0
        self.co2status = 0
        self.tx_pin = Pin(bind_pin('mh_z19c_tx', tx_pin))
        self.rx_pin = Pin(bind_pin('mh_z19c_rx', rx_pin))
        self.hd_pin = Pin(bind_pin('mh_z19c_hd', hd_pin), Pin.OUT, Pin.PULL_UP)
        self.start()

    def start(self):
        self.uart = UART(self.uart_no, baudrate=9600, tx=self.tx_pin, rx=self.rx_pin)
        self.uart.init(9600, bits=8, parity=None, stop=1, timeout=10)

    def stop(self):
        while self.uart.any():
            self.uart.read()
        self.uart.deinit()

    def _restart(self):
        self.stop()
        time.sleep(0.1)
        self.start()

    def get_data(self):
        try:
            while self.uart.any():
                self.uart.read()
            self.uart.write(b"\xff\x01\x86\x00\x00\x00\x00\x00\x79")
            time.sleep(0.1)
            s = self.uart.read(9)
        except Exception as e:
            console(f"MH-Z19 UART error: {e}")
            self._restart()
            return False

        if not s or len(s) != 9:
            return False
        if s[0] != 0xFF or s[1] != 0x86 or self._crc8(s) != s[8]:
            self._restart()
            return False
        self.ppm = s[2] * 256 + s[3]
        self.temp = s[4] - 40
        self.co2status = s[5]
        return True

    async def calibrate(self):
        with micro_task(tag=self.CALIBRATE_TASK) as my_task:
            try:
                self.stop()
                self.hd_pin.value(0)
                await my_task.feed(sleep_ms=8000)
                console("Calibration finished")
            except Exception as e:
                console(f"Calibration error: {e}")
            finally:
                self.hd_pin.value(1)
                self.start()

    @staticmethod
    def _crc8(a):
        crc = sum(bytearray(a)[1:8]) % 256
        crc = (~crc & 0xFF) + 1
        return crc

#########################
# Application functions #
#########################

def load(tx_pin=16, rx_pin=17, hd_pin=19):
    """
    Create MH-Z19 CO2 sensor (over UART)
    """

    if MHZ19.INSTANCE is None:
        MHZ19.INSTANCE = MHZ19(tx_pin=tx_pin, rx_pin=rx_pin, hd_pin=hd_pin)
    return MHZ19.INSTANCE


def measure():
    """
    Measure with MH-Z19 CO2 sensor
    """
    mhz19 = load()
    if not mhz19.get_data():
        return {"ppm": None, "temp": None, "status": None,
                "error": "No valid response from MH-Z19 sensor"}
    return {"ppm": mhz19.ppm,
            "temp": mhz19.temp,
            "status": mhz19.co2status}


def calibrate():
    """
    Calibrate MH-Z19 sensor
    """
    mhz19 = load()
    return micro_task(tag=MHZ19.CALIBRATE_TASK, task=mhz19.calibrate())


async def _run_sensor_loop(interval, topic, channels):
    channels = [] if channels is None else channels
    with micro_task(tag=MHZ19.SENSOR_TASK) as my_task:
        while True:
            my_task.out = "Start measurement"
            out = notify(json.dumps(measure()), topic=topic, channels=channels)
            my_task.out = f"Measurement published: {out}, wait {interval}ms"
            await my_task.feed(sleep_ms=interval)


def start(interval:int=5000, topic:str="MH_Z19C", channels:list=None):
    """
    Start sensor measurement loop and publish results over micros notify feature
    :param interval: update interval in milliseconds
    :param topic: for MQTT channel, default: MH_Z19C
    :param channels: selected notification channels, ex.: ["MQTT"], default: None (all)
    """
    load()
    return micro_task(tag=MHZ19.SENSOR_TASK, task=_run_sensor_loop(interval, topic, channels))


def stop():
    """
    Stop sensor measurement loop and publish, delete MHZ19.INSTANCE
    """
    manage_task(MHZ19.SENSOR_TASK, "kill")
    mhz19 = MHZ19.INSTANCE
    if mhz19 is not None:
        mhz19.stop()
        MHZ19.INSTANCE = None
    return f"{MHZ19.SENSOR_TASK}: Stopped"

#######################
# LM helper functions #
#######################

def pinmap():
    """
    [i] micrOS LM naming convention
    Shows logical pins - pin number(s) used by this Load module
    - info which pins to use for this application
    :return dict: pin name (str) - pin value (int) pairs
    """
    return pinmap_search(['mh_z19c_tx', 'mh_z19c_rx', 'mh_z19c_hd'])


def help(widgets=False):
    """
    [i] micrOS LM naming convention - built-in help message
    :return tuple:
        (widgets=False) list of functions implemented by this application
        (widgets=True) list of widget json for UI generation
    """
    return resolve(('load tx_pin=16 rx_pin=17 hd_pin=19',
                    'BUTTON start interval=5000',
                    'BUTTON stop', 'TEXTBOX measure', 'calibrate', 'pinmap'), widgets=widgets)
