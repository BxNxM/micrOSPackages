# Ultrasonic Distance Sensors

micrOS package for trigger/echo ultrasonic distance sensors.

It includes two load modules that share the same timing and distance math:

```text
hcsr04    -> HC-SR04
rcwl1670  -> RCWL-1670
```

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/ultrasonic_distance"
```

```bash
pacman upgrade "ultrasonic_distance"
pacman uninstall "ultrasonic_distance"
```

## Device Layout

- Package files: `/lib/ultrasonic_distance`
- Load modules: `/modules/LM_hcsr04.py`, `/modules/LM_rcwl1670.py`

> Based on pacman.json

## Wiring

```text
HC-SR04 VCC      -> 5V
HC-SR04 GND      -> GND
HC-SR04 TRIG     -> MCU output pin
HC-SR04 ECHO     -> MCU input pin

RCWL-1670 VCC    -> 3-5V
RCWL-1670 GND    -> GND
RCWL-1670 RX/TRIG -> MCU output pin
RCWL-1670 TX/ECHO -> MCU input pin
```

Default micrOS logical pins:

```text
hcsr04:
  hcsrtrig -> board-specific micrOS pin map
  hcsrecho -> board-specific micrOS pin map

rcwl1670:
  rcwl1670_trig -> GPIO16
  rcwl1670_echo -> GPIO17
```

## Pulse Protocol

```text
1. Pull trigger low briefly
2. Pull trigger high for 10 us
3. Pull trigger low
4. Measure high-pulse duration on echo
5. distance_cm = duration_us * 0.0343 / 2
```

## Usage

```commandline
hcsr04 load
hcsr04 measure_mm
hcsr04 measure_cm
hcsr04 deinit

rcwl1670 load trig_pin=16 echo_pin=17
rcwl1670 measure_mm
rcwl1670 measure_cm
rcwl1670 deinit
rcwl1670 pinmap
```

Both load modules return only the requested unit:

```python
{"mm": 171}
{"cm": 17.18213058419244}
```

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#external-modules)

## Dependencies

Dependencies are auto installed by `mip` based on `package.json`

```text
n/a
```
