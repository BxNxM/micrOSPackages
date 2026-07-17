# micrOS Application: rcwl1670

RCWL-1670 waterproof ultrasonic distance sensor driver for micrOS devices. HC-SR04 compatible, supports 2cm–400cm range at 3.3V or 5V. Returns distance in millimeters.

## Install

```bash
pacman install "github:fmandl/micrOSPackages/rcwl1670"
```

```bash
pacman upgrade "rcwl1670"
pacman uninstall "rcwl1670"
```

## Package Structure

```
rcwl1670/package/
└── LM_rcwl1670.py    # micrOS shell interface + HC-SR04 GPIO driver
```

## Hardware

- **Module**: RCWL-1670 (HC-SR04 compatible, waterproof, transceiver split)
- **Interface**: GPIO (TRIG + ECHO)
- **Voltage**: 3.3V or 5V (use 3.3V with ESP32 to avoid level shifting)
- **Range**: 2cm – 400cm
- **Tested on**: Seeed Studio ESP32-C6

## Pin Configuration

| Function | Default GPIO | Description |
|----------|-------------|-------------|
| TRIG | 16 | Trigger output (ESP → sensor) |
| ECHO | 17 | Echo input (sensor → ESP) |

## Wiring (3.3V, no level shifter needed)

```
ESP32          RCWL-1670
3.3V    →      VCC
GND     →      GND
GPIO16  →      TRIG/RX
GPIO17  ←      ECHO/TX
```

## Usage

```commandline
rcwl1670 load
rcwl1670 load trig_pin=16 echo_pin=17
rcwl1670 measure
rcwl1670 unload
```

### Example output

```
rcwl1670 measure
> distance_mm: 342
```

Values above 4000mm (400cm) are filtered and returned as `error: timeout`.

## Notes

- This is a **driver only** — it returns raw distance in mm
- Application logic (water level calculation, thresholds, alerts) belongs in a separate LM module
- The sensor is HC-SR04 compatible: 10µs TRIG pulse, ECHO pulse width proportional to distance

## Tests

```bash
cd rcwl1670
python3 -m pytest tests/ -v
```

## Author

Flórián Mandl ([@fmandl](https://github.com/fmandl))
