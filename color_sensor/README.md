# 📦 micrOS Application: color\_sensor

TCS3472 color sensor integration for micrOS. It provides RGB and ambient-light measurements, sensor LED control, a NeoPixel color indicator, and optional NeoPixel matrix cluster demos.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/color_sensor"
```

```bash
pacman upgrade "color_sensor"
pacman uninstall "color_sensor"
```

## Device Layout

- Package files: `/lib/color_sensor`
- Load module: `/modules/LM_tcs3472.py`

## Usage

```commandline
tcs3472 load
tcs3472 load led_pin=20 i2c_sda=None i2c_scl=None neop=None
tcs3472 measure
tcs3472 led state=True br=20
tcs3472 led state=False
tcs3472 indicator br=5
tcs3472 neomatrix_update
tcs3472 neomatrix_animation
tcs3472 pinmap
```

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#tcs3472)

## Dependency

Dependencies are auto installed by `mip` based on `package.json`

### built-ins

```text
LM_neopixel
LM_cluster
```
