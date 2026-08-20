# ![logo](https://raw.githubusercontent.com/BxNxM/micrOS/master/media/logo_mini.png) micrOS Packages 📦 v0.2

# micrOS Packages Registry and Tools

This repository contains multiple installable [micrOS](https://github.com/BxNxM/micrOS) packages and applications.  
Each package lives in its own folder and includes a **package.json** file compatible with `mip`.  
micrOS devices can install these packages from GitHub or from a local `mip` server.  
In addition to `package.json`, micrOS packages also include a **pacman.json** file for package lifecycle management.

---

# 📦 Package Catalog

| Project | Load module(s) | Short description |
| --- | --- | --- |
| [alarm_system](./alarm_system/README.md) | `alarm_system` | Distributed alarm system with local and MQTT zones, event logging, and supervision. |
| [async_mqtt](./async_mqtt/README.md) | `mqtt_client` | Async MQTT client with micrOS Notifications integration. |
| [async_oledui](./async_oledui/README.md) | `oledui` | SSD1306 and SH1106 OLED GUI with trackball support. |
| [blinky_example](./blinky_example/README.md) | `blinky` | Minimal package example implementing basic `Pin.OUT` operations. |
| [co2](./co2/README.md) | `mh_z19c`<br>`mq135` | MH-Z19 NDIR CO2 and MQ-135 air-quality sensor integrations. |
| [color_sensor](./color_sensor/README.md) | `tcs3472` | TCS3472 RGB and ambient-light sensor with NeoPixel indicator support. |
| [garage_remote](./garage_remote/README.md) | `garage` | Smart garage remote control integrated with `phone_manager`. |
| [keychaindemo](./keychaindemo/README.md) | `keychain` | ESP32-C3 OLED keychain demo with temperature sensing and NeoPixel control. |
| [neopixel_matrix](./neopixel_matrix/README.md) | `neomatrix` | NeoPixel matrix animations, frame playback, and web control. |
| [phone_manager](./phone_manager/README.md) | `users` | Phone number-based user management and access control. |
| [qr_code](./qr_code/README.md) | — | Standalone QR Code generator for CPython and MicroPython. |
| [ultrasonic_distance](./ultrasonic_distance/README.md) | `hcsr04`<br>`rcwl1670` | HC-SR04 and RCWL-1670 ultrasonic trigger/echo distance sensors. |
| [sim800](./sim800/README.md) | `sim800`<br>`sim800_http`<br>`sim800mqtt` | SIM800C voice, SMS, USSD, HTTP, and MQTT integration. |
| [sound_event](./sound_event/README.md) | `sound_event` | Trainable I2S microphone sound-event recognition with labeled datasets. |
| [tof_distance](./tof_distance/README.md) | `VL53L0X` | VL53L0X time-of-flight distance sensor integration. |


---

```
______               _                                  _   
|  _  \             | |                                | |  
| | | |_____   _____| | ___  _ __  _ __ ___   ___ _ __ | |_ 
| | | / _ \ \ / / _ \ |/ _ \| '_ \| '_ ` _ \ / _ \ '_ \| __|
| |/ /  __/\ V /  __/ | (_) | |_) | | | | | |  __/ | | | |_ 
|___/ \___| \_/ \___|_|\___/| .__/|_| |_| |_|\___|_| |_|\__|
                            | |                             
                            |_|                             
```

# CLI Tool (`tools.py`)

The `tools.py` script provides a unified interface to validate packages, run package unit tests, create new packages, update package metadata, and start a local `mip` package registry server.

## Usage

```bash
python3 tools.py [options]
```

## Options

### General
- `-h`, `--help`
  Show help message and exit.

### Validation
- `-v [VALIDATE]`, `--validate [VALIDATE]`  
  Validate one package by name.  
  If no name is provided, validate all packages.

### Unit Tests
- `-ut UNIT_TEST`, `--unit-test UNIT_TEST`  
  Run unit tests for one package if `<package>/tests` exists with the normal pytest output.  
  If no name is provided, run all available package unit tests.  
  Use `-q` for short one-line summaries.

### Local mip Server
- `-s`, `--serve`  
  Start the local mip package registry server.

### Package Creation
- `-c`, `--create`  
  Create a new micrOS application package from the template.
- `--package PACKAGE`  
  Name of the package/application when creating a new one.
- `--module MODULE`  
  Public Load Module name (LM_*.py) when creating a new application.

### Update package.json
- `-u UPDATE`, `--update UPDATE`  
  Update the `package.json` file of a package by its `PACKAGE` name.  
  Primarily updates the "urls" section.

---

# Repository Structure

```bash
➜  micrOSPackages git:(main) ✗ tree -L 3     
.
├── README.md
├── _tools                                  <- PACKAGE CREATION AND MAINTENANCE SCRIPTS
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── __init__.cpython-312.pyc
│   │   ├── create_package.cpython-312.pyc
│   │   ├── mip.cpython-312.pyc
│   │   ├── serve_packages.cpython-312.pyc
│   │   ├── unpack.cpython-312.pyc
│   │   └── validate.cpython-312.pyc
│   ├── app_template
│   │   ├── README.md
│   │   ├── package
│   │   └── package.json
│   ├── create_package.py
│   ├── mip.py
│   ├── serve_packages.py
│   ├── unpack.py
│   ├── ut_executor.py
│   └── validate.py
├── async_mqtt                              <- APPLICATION PACKAGE
│   ├── README.md
│   ├── package
│   │   ├── LM_mqtt_client.py
│   │   ├── __init__.py
│   │   └── pacman.json
│   └── package.json
├── async_oledui                            <- APPLICATION PACKAGE
│   ├── README.md
│   ├── package
│   │   ├── LM_oledui.py
│   │   ├── __init__.py
│   │   ├── pacman.json
│   │   ├── peripheries.py
│   │   └── uiframes.py
│   └── package.json
├── blinky_example                          <- APPLICATION PACKAGE
│   ├── README.md
│   ├── package
│   │   ├── LM_blinky.py
│   │   ├── __init__.py
│   │   └── pacman.json
│   └── package.json
└── tools.py
```

> `package.json`: **MicroPython** standard for `mip` installations

> `pacman.json`: OAM metadata for **micrOS** package unpack, update, and delete


### Load Module Naming Convention

micrOS automatically loads modules only if their filenames match:

```
LM_*.py
```

---

# Validating Packages

Validate all packages:

```bash
python3 tools.py --validate
```

Validate one specific package:

```bash
python3 tools.py --validate mypackage
```

The validation process ensures:
- `package.json` exists
- all files listed inside `package.json` actually exist
- the package structure is valid for `mip` installation
- `pacman.json` exists
- available unit tests under `<package>/tests` pass

Run unit tests directly for one package:

```bash
python3 tools.py --unit-test mypackage
```

Run all available package unit tests:

```bash
python3 tools.py --unit-test
```

---

# Updating `package.json`

Update the `urls` section of a package's `package.json`:

```bash
python3 tools.py --update mypackage
```

> `package.json` (`urls`) generation for all `/package` files

> `pacman.json` metadata generation from `package.json`

---

# Creating a New micrOS Package

```bash
python3 tools.py --create --package myapplication --module myapp
```


This command:
- creates a new folder
- copies the template structure
- fills in `package.json` with the provided values

---

# Local `mip` Test Server

Start the local mip package registry server:

```bash
python3 tools.py --serve
```

### Output:

```
➜  micrOSPackages git:(main) ✗ ./tools.py --serve
Starting server...
🚀 Serving repo root: /Users/bnm/micrOS/micrOSPackages
🌐 HTTP server: http://0.0.0.0:8000/
📡 Detected local IP: http://10.0.1.73:8000/

📦 Available mip packages in repo root:

  • async_mqtt
    🧪 Test with curl:     curl http://10.0.1.73:8000/async_mqtt/package.json | jq .
    👉 On device (repl):   import mip; mip.install('http://10.0.1.73:8000/async_mqtt/')
    👉 On device (shell):  pacman install 'http://10.0.1.73:8000/async_mqtt/'
  • async_oledui
    🧪 Test with curl:     curl http://10.0.1.73:8000/async_oledui/package.json | jq .
    👉 On device (repl):   import mip; mip.install('http://10.0.1.73:8000/async_oledui/')
    👉 On device (shell):  pacman install 'http://10.0.1.73:8000/async_oledui/'
  • blinky_example
    🧪 Test with curl:     curl http://10.0.1.73:8000/blinky_example/package.json | jq .
    👉 On device (repl):   import mip; mip.install('http://10.0.1.73:8000/blinky_example/')
    👉 On device (shell):  pacman install 'http://10.0.1.73:8000/blinky_example/'

🛠️ Press Ctrl+C to stop.
```

---

# Installing Packages on a micrOS Device

## From GitHub (REPL)

```python
import mip
mip.install("github:BxNxM/micrOSPackages/blinky_example")
```

## From Shell

```bash
pacman install "https://github.com/BxNxM/micrOSPackages/blob/main/blinky_example"
```

---

# Summary

- Each folder is one micrOS package.
- `tools.py` manages:
  - validation
  - unit test execution
  - package creation
  - `package.json` updating
  - local `mip` server
- `validate.py` checks package structure and file references.
- `ut_executor.py` runs package-local pytest suites from `<package>/tests`.
- `serve_packages.py` provides a local `mip` server.
- Load Modules must follow the `LM_*.py` naming pattern.


# Improvement ideas

```text
- Cross compile packages with mpy-cross
	- Adapt pacman to prioritize .mpy files

- Add explicit tag/branch flag support for mip wrappers 
```


```bash
git push -u origin main
```
