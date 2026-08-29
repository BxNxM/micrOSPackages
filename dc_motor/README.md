![motor_l298n illustration](./media/motor_l298n.png?raw=true)

# 📦 micrOS Application: dc_motor

One-line summary of the package.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/dc_motor"
```

```bash
pacman upgrade "dc_motor"
pacman uninstall "dc_motor"
```

## Device Layout

- Package files: `/lib/dc_motor`
- Load modules: `/modules/LM_*`
- Web assets: `/web/*` when present

> Based on pacman.json

## Usage

### motor_l298n

```commandline
load pwm_freq=None ena_pin=10 ina_pin=12 inb_pin=11 enb_pin=3 inc_pin=9 ind_pin=40
speed motor=<1/2> speed=<0-1023>
direction motor=<1/2> forward=<True/False>
coast motor=<1/2>
brake motor=<1/2>
state motor=<0/1/2>
pinmap
```

### motor_l9110

```commandline
load dir_1_pin=None dir_2_pin=None
motor_control direc=<0/1> speed=<0-1000>
pinmap
```

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#external-modules)

## Dependencies

Dependencies are auto installed by `mip` based on `package.json`

```text
n/a
```
