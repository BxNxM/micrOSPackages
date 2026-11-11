# micrOS Bluetooth shell

Optional BLE Nordic UART Service (NUS) for MicroPython on BLE-capable ESP32
variants. The package wraps the existing `Shell.Shell`: the same hello, password,
configuration and Load Module commands work over Bluetooth. `Shell.py` is unchanged.
No extra on-board Python dependencies are needed.

## Install and start

From the existing micrOS shell, after publishing these package files:

```text
pacman install "github:BxNxM/micrOSPackages/bluetooth"
bluetooth load
bluetooth status
bluetooth stop
```

`load` always uses `cfgget("devfid")` as its advertised name and takes no
parameters. The configured name must be 1–29 UTF-8 bytes. Stop and load again
after changing `devfid` to refresh the advertised name.
Loading is idempotent; the managed worker activates the radio on its first
scheduled step. Stop disconnects and shuts down the radio. Allow the worker
to finish before loading again. Task tag: `bluetooth.shell`.

Requires firmware providing `bluetooth.BLE` and exclusive ownership of the
controller; load refuses an already active radio. ESP32-S2 lacks Bluetooth.
Other ESP32 variants require the appropriate BLE-capable firmware image.
There is no automatic boot activation or core configuration change.

Installed payload:

- `/modules/LM_bluetooth.py`: lazy shell/REST frontend.
- `/lib/bluetooth/Bluetooth.py`: unified native BLE, advertising, GATT transport,
  Shell integration and service lifecycle.
- `/lib/bluetooth/pacman.json`: lifecycle receipt.

MicroPython can treat `/lib/bluetooth` as a namespace package even without
`__init__.py`, shadowing its native `bluetooth` module. The shared `firmware()`
loader temporarily clears `sys.path` to force the native module, restores the
original path in `finally`, and caches the BLE implementation. A missing native
`BLE`/`UUID` API produces an explicit BLE-enabled-firmware error.
The entrypoint adds `/lib/bluetooth` (resolved through
`Files.OSPath.LIB`) to the import search path when first loaded, then imports
the uppercase `Bluetooth` core. All runtime implementation lives in that
single file. The macOS tester and host tests are excluded from the manifest.

## Source responsibilities

```text
package/
├── Bluetooth.py             # Unified implementation, organized by responsibility
├── LM_bluetooth.py          # Thin load/stop/status/help frontend
└── pacman.json              # Package lifecycle metadata
```

The `helpers/ble_shell.py` macOS client and `tests/` remain outside the installed
payload. Firmware Bluetooth and Shell imports stay lazy until activation.

Other on-device frontends can use the same core after adding
`Files.path_join(Files.OSPath.LIB, 'bluetooth')` to `sys.path`:

```python
import Bluetooth
Bluetooth.load()    # Initializes NUS and advertises cfgget("devfid")
Bluetooth.status()  # Shared service state
Bluetooth.stop()    # Disconnects and releases the controller
```

Both Python callers and `LM_bluetooth` control the same service instance and
managed task. The core imports no hardware or Shell backend until activation.
`Shell.py` remains unchanged.

## Local package server and real-board verification

From the repository root, start the mip development server:

```bash
python3 micrOS/packages/tools.py --serve
```

Use the LAN URL printed for `bluetooth` (not localhost) in the board's existing
Wi-Fi shell. For example, substituting the server's printed IP:

```text
pacman install "http://<mac-lan-ip>:8000/bluetooth/"
bluetooth load
bluetooth status
```

`load` schedules initialization, registers NUS, and begins connectable
advertising. The client can then connect and use the same shell commands.
Check status and task output again after the worker has run. Errors are logged
through `Common.syslog`; use `system alarms dump=True` to inspect them. No separate
advertise or accept command is required.

Run the macOS smoke test below, reconnect with an interactive session, then
try `hello`, `version`, `help`, `conf`, `devfid`, `noconf`, and `exit`. Reconnect
again to verify fresh authentication and command mode. Test longer responses
and repeat connection/disconnection with the normal Wi-Fi workload. Finally,
use the Wi-Fi shell to run `bluetooth stop` and check inactive status; another
`bluetooth load` should advertise again.

When reinstalling changed files on a board that already imported this package,
stop the listener and reboot the board before testing the new code; MicroPython
keeps imported modules cached. Rebooting is unnecessary for a first installation.
Older installations may still contain the former `micros_ble` directory:
normal `mip` reinstalls do not prune removed files. A clean package uninstall
before installation removes that obsolete directory; the unified core never
imports it.

The server serves a locally rewritten manifest; the committed manifest continues
to reference the GitHub package. Stop the server with Ctrl-C when finished.

## macOS terminal and smoke test

Run from the micrOS repository on the Mac (CPython 3.9+):

```bash
python3 -m venv /tmp/micros-ble-env
source /tmp/micros-ble-env/bin/activate
python3 -m pip install bleak
python3 micrOS/packages/bluetooth/helpers/ble_shell.py --scan
python3 micrOS/packages/bluetooth/helpers/ble_shell.py --name TinyDevBoard --test
python3 micrOS/packages/bluetooth/helpers/ble_shell.py --name TinyDevBoard
python3 micrOS/packages/bluetooth/helpers/ble_shell.py --name TinyDevBoard -c hello -c "system info"
```

Replace `TinyDevBoard` with the board's configured `devfid`. If names collide, select
`--address <UUID>` from the scan output; macOS uses a device UUID, not a MAC
address. Grant the terminal/application Bluetooth access in macOS Privacy &
Security settings. The tester scans only NUS advertisements, subscribes to TX,
then sends an empty line to request the initial prompt. It prompts privately
for the node password when shell authentication is enabled. Passwords are not
command-line arguments. `--test` checks hello, version and help; any missing
response, timeout or early disconnect fails with a nonzero exit code.
The response parser learns the node prompt and requires it on a complete line;
arbitrary ` $ ` text in output does not end a command. The timeout covers both
GATT writes and the response. Use `--timeout 60` for long commands. Interactive `exit` closes the connection;
Ctrl-C quits. Use an interactive session for configuration mode.

A phone or other client must support **BLE NUS**, not Classic SPP. Subscribe to
TX notifications before sending commands. Send an empty line for the initial
prompt; the board does not send an unsolicited prompt before subscription.

## micrOS task integration

The runtime follows [MODULE_GUIDE.md](../../MODULE_GUIDE.md#micro_tasktag-tasknone-_wrapfalse):
`Common.micro_task` creates the `bluetooth.shell` worker, which enters its managed
task context and writes lifecycle details to `task.out`. All idle waits,
notification pacing and busy retries use `await task.feed(sleep_ms=...)`, keeping
the micrOS watchdog fed while yielding cooperatively. There are no direct
`asyncio` or `Tasks` imports in the installed package. The standalone macOS
helper uses CPython's asyncio independently.

The low-level `Peripheral` async operations use the task bound by the worker;
application callers should initialize through `Bluetooth.load()`. Intentional
stop/disconnect or a replaced session during output does not become a spurious
transport error on the stopped or new session.

## Startup diagnostics

```text
bluetooth load
bluetooth status
task show bluetooth.shell
```

The managed task writes its current lifecycle stage to `.out`, so `task show`
reports messages such as `BLE activating radio: TinyDevBoard`,
`BLE registering NUS: TinyDevBoard`, `BLE advertising: TinyDevBoard`,
`BLE connected: TinyDevBoard`, or the generic `BLE error: TinyDevBoard` marker. It does not record
shell input, passwords or command replies.

`status` contains `active`, `connected`, `advertising`, and `state`. Its `state`
value is the exact managed `task.out` message displayed
by `task show bluetooth.shell`; there is no separate server state field. Immediately after load the task may be `starting`; `active` means
the service is scheduled/running. Advertising is reported only after the BLE
advertise call succeeds. A connected client stops advertising, so disconnect
other terminal/phone clients before scanning again. Startup and session errors
are written through `Common.syslog` with an `[ERR] Bluetooth:` prefix. Error
details live in the system log; there is no cached error attribute in status.

## Transport behavior

- One connection; a new Shell instance on every reconnect. Existing `auth` and
  `appwd` apply; failed authentication disconnects. `hello` retains Shell's
  existing unauthenticated behavior. `exit` sends Bye and disconnects.
- RX accepts Write and Write Without Response; TX uses notifications.
  Service UUID: `6E400001-B5A3-F393-E0A9-E50E24DCCA9E`;
  RX ends in `0002`, TX in `0003` (same UUID suffix).
- LF, CR and CRLF delimit commands. Fragments and split UTF-8 are reassembled;
  multiple lines per write execute in order. Empty lines request a prompt.
- Maximum command: 512 UTF-8 bytes. Pending input is bounded at 1024 bytes;
  the GATT buffer has a 1025-byte overflow sentinel. Invalid UTF-8 or detected
  overflow disconnects instead of executing truncated commands. Driver-level
  event loss remains possible under excessive traffic: pace client writes.
- Commands execute serially in the managed async worker. IRQ callbacks only
  handle connection state and bounded input collection. Worker polls at 20 ms.
- Output is UTF-8, newline-separated except for the shell prompt, split into
  20-byte notifications with 15 ms cooperative pacing. Busy sends retry up to
  five times. There is no application delivery acknowledgement; long output
  and radio coexistence need testing on each target.
- Disconnect discards session input/auth/config state and resumes advertising. If
  advertising fails to restart, run `bluetooth load` again to retry.
  Stop or task cancellation releases the controller. Transport failures are
  logged through `Common.syslog`; normal disconnects and stops are not errors.

Shell authentication does not encrypt BLE traffic. This initial implementation
has no pairing/bonding or encrypted characteristic requirement, so use it only
where transmitting shell commands and passwords without BLE encryption is
acceptable. BLE shares resources with Wi-Fi/ESP-NOW; measure heap, latency and
reliability on your chosen ESP32 image.

## Validation

```bash
python3 -m pytest -q micrOS/packages/bluetooth/tests
python3 micrOS/packages/tools.py -v bluetooth -q
python3 devToolKit.py -lint
```

Host tests exercise the real `Shell.py` with fake hardware/config dependencies,
including framing, authentication, configuration, exit/reconnect, notification
chunking/retries, overflow, cancellation before startup, startup failures,
and client timeouts. An end-to-end host test connects the actual macOS tester
to the wrapper and real shell through fake BLE. They do not prove BLE radio behavior.
The macOS tester is the real-board validation entrypoint. Test reconnects,
long output and simultaneous Wi-Fi activity on each board before deployment.

The original [feasibility study](STUDY.md) records the dependency decision and
primary references. Its proposed implementation section is historical.
