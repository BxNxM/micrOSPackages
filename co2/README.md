# micrOS CO2 sensor package

micrOS load modules for two different sensor families:

- `mh_z19c`: UART driver for MH-Z19B/MH-Z19C NDIR CO2 sensors.
- `mq135`: analog MQ-135 air-quality sensor with a calibrated CO2-equivalent
  estimate.

The MQ-135 is not a selective CO2 sensor. Its estimate is affected by other
gases, warm-up time, supply voltage, and calibration. Use an MH-Z19 sensor when
an actual CO2 measurement is required.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/co2"
```

```bash
pacman upgrade "co2"
pacman uninstall "co2"
```

## Wiring

The logical pin names can be inspected on-device:

```text
mh_z19c pinmap
mq135 pinmap
```

Default MH-Z19 pin fallbacks are TX 16, RX 17, and HD 19. The sensor uses
9600 baud UART. Confirm voltage and ADC limits for your board before connecting
an MQ-135 module; many breakout boards expose an analog voltage above the safe
range of a 3.3 V MCU.

## Usage

### MH-Z19B/MH-Z19C

```text
mh_z19c load tx_pin=16 rx_pin=17 hd_pin=19
mh_z19c measure
mh_z19c start interval=5000 topic=MH_Z19C
mh_z19c stop
```

`measure` returns `ppm`, `temp`, and the sensor status byte. On a timeout,
malformed frame, or checksum failure it returns those fields as `null` plus an
`error` field.

Zero calibration drives the HD pin low for eight seconds:

```text
mh_z19c calibrate
```

Only calibrate after the sensor has warmed up in stable outdoor air near
400 ppm. Calibration changes the sensor baseline; do not run it as a routine
measurement command.

### MQ-135

```text
mq135 load pin=None
mq135 raw_measure_mq135
mq135 measure_mq135 temperature=23 humidity=45
```

The formula uses a fixed `RZERO` of 76.63 kΩ. For meaningful results, burn in
the sensor and determine an installation-specific `RZERO` using a trusted
reference instrument.

## Device layout

- Package files: `/lib/co2`
- Load modules: `/modules/LM_*`
- Metadata: `/lib/co2/pacman.json`

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#external-modules)

## Test

From the package registry root:

```bash
python3 tools.py -ut co2
python3 tools.py -v co2
```

## Dependencies

Dependencies are auto installed by `mip` based on `package.json`

No external package dependencies.
