![irrigation illustration](./media/irrigation.png?raw=true)

# micrOS Package: irrigation\_system - WIP (beta)

Architecture-first skeleton for a water-only garden irrigation dashboard.

The public load module is `aqua`. This first version does not drive real
hardware yet; it provides the package shape, web UI, dummy API endpoints, and
the core tank/flow/head calculations that the real pump and sensor logic can
replace later.

## Install

```bash
pacman install "github:BxNxM/micrOSPackages/irrigation_system"
```

```bash
pacman upgrade "irrigation_system"
pacman uninstall "irrigation_system"
```

## Device Layout

- Load module: `/modules/LM_aqua.py`
- Package metadata: `/lib/irrigation_system/pacman.json`
- Web UI: `/web/irrigation_system/aqua.html`

## Usage

```commandline
aqua load
aqua status
aqua configure tank_width_cm=40 tank_depth_cm=25 tank_height_cm=20 water_distance_cm=7 level_module=manual pump_l_hour=300 head_count=4 soil_sensor_count=4
aqua configure level_module=rcwl1670
aqua sensor_distance
aqua plan volume_l=1
aqua plan per_head_l=0.25
aqua water volume_l=1
task show aqua._watering_task
aqua stop
```

Open the dashboard after `aqua load`:

```text
http://<device>/aqua
http://<device>/irrigation
```

## Skeleton API

- `GET /aqua/api` returns the dummy dashboard state.
- `POST /aqua/api` accepts `status`, `configure`, `water`, `stop`, `set_level`, and `measure_level` actions.
- `/irrigation/api` is an alias for the same API.

The current model includes:

- tank dimensions and top-to-water distance measurement
- ultrasonic distance sensor integration through the `ultrasonic_distance` package
- default no-sensor/manual mode with `water_distance_cm` test input
- selectable real level modules: `rcwl1670` or `hcsr04`
- minimum reserve threshold
- pump flow in L/h
- configurable number of irrigation heads
- configurable number of soil moisture sensors
- short-lived `aqua._watering_task` with `task.out` progress while watering
- calculated tank capacity, water height, current volume, usable volume, per-head flow, and run plan

## Dependencies

```text
ultrasonic_distance
```
