![veml7700 illustration](./media/veml7700.png?raw=true)
![tempt6000 illustration](./media/tempt6000.png?raw=true)

# 📦 micrOS Application: light_sensors

Analog TEMPT6000 light intensity and illuminance measurements, plus digital
VEML7700 lux measurements. Includes the legacy `light_sensor` commands for
compatibility.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/light_sensors"
```

```bash
pacman upgrade "light_sensors"
pacman uninstall "light_sensors"
```

## Device Layout

- Package files: `/lib/light_sensors`
- Load modules: `/modules/LM_tempt6000.py`, `/modules/LM_veml7700.py`,
  and `/modules/LM_light_sensor.py`

## Usage

TEMPT6000 (ADC, logical pin `temp6000`):

```commandline
tempt6000 load
tempt6000 intensity
tempt6000 illuminance
tempt6000 pinmap
```

VEML7700 (I2C, logical pins `i2c_scl` and `i2c_sda`):

```commandline
veml7700 load
veml7700 read_lux
veml7700 pinmap
```

## Compatibility

Install this package to keep using the original `light_sensor` and `veml7700`
commands after their removal from the built-in modules.

`light_sensor` forwards `load`, `intensity`, `illuminance`, `subscribe_intercon`,
`pinmap`, and `help(widgets=False)` to `tempt6000`, preserving their arguments
and return values. Both names share the same sensor instance and the existing
`light_sensor.intercon` task.

```commandline
light_sensor intensity
light_sensor illuminance
light_sensor subscribe_intercon "lamp.local switch set_state True" "lamp.local switch set_state False" threshold=4 tolerance=2 sample_sec=60
```

Existing shell commands, REST calls, hooks, and the Prometheus/Grafana setup
using `light_sensor` can retain their current names. The `veml7700` command
name and API are unchanged.

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#external-modules)

## Dependencies

No additional packages are required. The drivers use micrOS firmware APIs
and MicroPython hardware support.
