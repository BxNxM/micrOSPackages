"""
LM_Blinky.py – Simple LED blinker Load Module for micrOS.

This module exposes a few basic functions over micrOS:

- load(pin_number=26)  → initialize the LED pin
- on()                 → LED ON
- off()                → LED OFF
- toggle()             → toggle LED state
- blink(count=10, delay_ms=200) → blink LED N times with delay
- help()               → list available functions

All functions are callable from ShellCli / WebCli.
"""

from machine import Pin
from microIO import bind_pin
import utime as time  # Micropython-friendly time module


# Global cache of the LED Pin instance
LED = None


def load(pin_number=26):
    """
    Initialize and cache the LED pin.

    :param pin_number: physical GPIO number (default: 26)
    :return: Pin instance
    """
    global LED
    if LED is None:
        # Reserve this pin for the 'led' tag and get the real pin number
        pin = bind_pin('led', pin_number)
        LED = Pin(pin, Pin.OUT)
    return LED


def on():
    """
    Turn the LED ON.
    :return: status string
    """
    pin = load()
    pin.value(1)
    return "Blinky: LED ON"


def off():
    """
    Turn the LED OFF.
    :return: status string
    """
    pin = load()
    pin.value(0)
    return "Blinky: LED OFF"


def toggle():
    """
    Toggle LED state.
    :return: status string with new state
    """
    pin = load()
    pin.value(not pin.value())
    return "Blinky: LED ON" if pin.value() else "Blinky: LED OFF"


def blink(count=10, delay_ms=200):
    """
    Blink the LED a given number of times with blocking delay.

    :param count: how many times to toggle ON/OFF (default: 10)
    :param delay_ms: delay between toggles in milliseconds (default: 200)
    :return: status string when finished
    """
    pin = load()

    for _ in range(count):
        pin.value(1)
        time.sleep_ms(delay_ms)
        pin.value(0)
        time.sleep_ms(delay_ms)

    return "Blinky: blink sequence finished"


def help(widgets=False):
    """
    micrOS LM naming convention - built-in help message.

    :param widgets: kept for compatibility, not used here
    :return: tuple of exported function names
    """
    return (
        "load pin_number=26",
        "on",
        "off",
        "toggle",
        "blink count=10 delay_ms=200",
    )
