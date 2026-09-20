"""LEGACY: Compatibility commands for the TEMPT6000 light sensor."""

import LM_tempt6000 as _tempt6000


def load():
    """Initialize the TEMPT6000 light sensor."""
    return _tempt6000.load()


def intensity():
    """Measure light intensity in percent."""
    return _tempt6000.intensity()


def illuminance():
    """Measure light illuminance in lux."""
    return _tempt6000.illuminance()


def subscribe_intercon(on, off, threshold=4, tolerance=2, sample_sec=60):
    """Send ON/OFF commands when light crosses the configured threshold."""
    return _tempt6000.subscribe_intercon(on, off, threshold=threshold,
                                       tolerance=tolerance, sample_sec=sample_sec)


def pinmap():
    """Show the logical pin used by the sensor."""
    return _tempt6000.pinmap()


def help(widgets=False):
    """Show commands or dashboard widgets for the sensor."""
    return _tempt6000.help(widgets=widgets)
