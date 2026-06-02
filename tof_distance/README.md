# 📦 micrOS Application: tof\_distance

VL53L0X time-of-flight distance sensor integration for micrOS. It initializes the I2C sensor and exposes single-shot distance measurements in millimeters.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/tof_distance"
```

```bash
pacman upgrade "tof_distance"
pacman uninstall "tof_distance"
```

## Device Layout

- Package files: `/lib/tof_distance`
- Load module: `/modules/LM_VL53L0X.py`

## Usage

```commandline
VL53L0X measure
VL53L0X pinmap
```

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#VL53L0X)

## Dependency

Dependencies are auto installed by `mip` based on `package.json`

### built-ins

```text
n/a
```
