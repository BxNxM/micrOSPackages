![roboarm illustration](./media/roboarm.png?raw=true)

# 📦 micrOS Application: roboarm

One-line summary of the package.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/roboarm"
```

```bash
pacman upgrade "roboarm"
pacman uninstall "roboarm"
```

## Device Layout

- Package files: `/lib/roboarm`
- Load modules: `/modules/LM_roboarm`

> Based on pacman.json

## Usage

```commandline
 control x=<40-115> y=<40-115> speed_ms=5 smooth=True,
 boot_move speed_ms=10,
 standby y_pos=45,
 jiggle delta=3,
 play 40 40 115 115 s=<speed ms> delay=<ms> deinit=True,
 play deinit=True,
 record clean=False rec_limit=8,
 random x_range=20 y_range=20 speed_ms=5,
 load servo_1_pin=None servo_2_pin=None switch_pin=None,
 pinmap,
 status,
```

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#external-modules)

## Dependencies

### Built-in dependecies

```
LM_servo
LM_switch
```

Dependencies are auto installed by `mip` based on `package.json`

```text
n/a
```
