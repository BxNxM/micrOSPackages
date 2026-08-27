# micrOS Application: neopixel_matrix

NeoPixel matrix package with pixel addressing, brightness control, animation helpers, file-based frame playback, and a small web drawing UI.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/neopixel_matrix"
pacman upgrade "neopixel_matrix"
pacman uninstall "neopixel_matrix"
```

## Device Layout

- Package files: `/lib/neopixel_matrix`
- Load module: `/modules/LM_neomatrix.py`
- Web assets: `/web/matrix_draw.html`, `/web/matrix_draw.js`
- Data animations: `/data/<file>.jsonl`

## Usage

```commandline
neomatrix load width=8 height=8 neop=14 i2c_sda=11 i2c_scl=12
pixel x y color=(10, 3, 0) show=True
clear
color_fill r=<0-255-5> g=<0-255-5> b=<0-255-5>
brightness br=<0-100>
stop
snake speed_ms=50 length=5
rainbow
spiral speed_ms=40
noise speed_ms=85
play_file file="animation.jsonl" speed_ms=85
control speed_ms=<1-200> bt_draw=None
draw_colormap bitmap=[(0,0,(10,2,0)),(x,y,color),...]
get_colormap
status
```

## Animation Files

`play_file` reads animation files from `/data`. The input must be a file name with extension, not a path.

Each non-empty line is one frame. A frame uses the same pixel data shape as `draw_colormap`, encoded as JSON:

```json
[[0,0,[10,2,0]],[1,0,[0,10,2]]]
[[0,1,[0,0,10]],[1,1,[10,10,0]]]
{"pixels":[{"x":2,"y":0,"color":{"r":10,"g":0,"b":2}}]}
{"3,0":[2,10,0]}
```

Example:

```commandline
neomatrix play_file file="animation.jsonl" speed_ms=85
```

## Web UI

Open `matrixDraw` from the micrOS web UI to draw frames.

- `Read Matrix` reads the current device state into the editor.
- `Add Frame` appends the current frontend matrix as a new frame line.
- `Export JSONL Frames` converts the frame lines into `/data` file format and copies the result.
- `Send REST Batches` sends the current matrix input directly with `draw_colormap`.

## Dependencies

No mandatory package dependencies.

On boards with the onboard QMI8658C sensor, `neomatrix load` can bind the shared
I2C pins for the sensor. Install the `gyro` package separately when you also
want the `qmi8658` shell commands:

```bash
pacman install "github:BxNxM/micrOSPackages/gyro"
```
