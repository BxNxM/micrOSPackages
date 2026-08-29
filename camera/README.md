![OV2640 illustration](./media/OV2640.png?raw=true)

# 📦 micrOS Application: camera

One-line summary of the package.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/camera"
```

```bash
pacman upgrade "camera"
pacman uninstall "camera"
```

## Device Layout

- Package files: `/lib/camera`
- Load modules: `/modules/LM_OV2640`

> Based on pacman.json

## Usage

```commandline
 load quality="medium/low/high" freq="default/high" flash_pin=4,
 settings quality=None flip=None mirror=None effect="NONE",
 settings saturation=<0-100>,
 settings brightness=<0-100>,
 settings contrast=<0-100>,
 settings effect=<NONE,NEG,BW,RED,GREEN,BLUE,RETRO>,
 capture,
 photo,
 flashlight state=None,
 pinmap,
 [Hint] after load you can access the /cam/snapshot and /cam/stream endpoints,
 Thanks to :) https://github.com/lemariva/micropython-camera-driver,
```

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#external-modules)

## Dependencies

Dependencies are auto installed by `mip` based on `package.json`

```text
n/a
```
