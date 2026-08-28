![trackball illustration](./media/trackball.png?raw=true)

# 📦 micrOS Application: trackball

Pimoroni [trackball](https://shop.pimoroni.com/products/trackball-breakout) (x,y,press+rgb) driver module.


## Install

```bash
pacman install "github:BxNxM/micrOSPackages/trackball"
```

```bash
pacman upgrade "trackball"
pacman uninstall "trackball"
```

## Usage

```commandline
 load width=100 height=100 irq_sampling=50 sensitivity=5,
 read,
 get,
 settings irq_sampling=None sensitivity=None,
 pinmap,
```

[documentation](https://htmlpreview.github.io/?https://github.com/BxNxM/micrOS/blob/master/micrOS/client/sfuncman/sfuncman.html#external-modules)

## Dependencies

Dependencies are auto installed by `mip` based on `package.json`

```text
n/a
```
