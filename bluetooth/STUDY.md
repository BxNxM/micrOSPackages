# Bluetooth shell for micrOS — feasibility study

Status: design and package scaffold, 2026-10-27. No Bluetooth service or Load
Module is implemented yet. Installing this scaffold only installs metadata.
Target: MicroPython on ESP32 variants; no changes to core boot behavior.

## Recommendation

Implement an optional BLE peripheral exposing Nordic UART Service (NUS),
with a small transport adapter subclassing `Shell.Shell`. Start with the
firmware's built-in `bluetooth` API: no additional Python packages are required.
This is the smallest dependency surface for a single service and single client;
actual RAM use and reliability still need measurement on hardware.

For simpler async connection management, the alternative is `aioble-peripheral`
plus `aioble-server` (both depend on `aioble-core`). MicroPython recommends
aioble for most applications. The full `aioble` distribution also includes
central, client, L2CAP and security components, unnecessary for the initial
unpaired UART peripheral. If direct IRQ handling becomes complex, prefer these
two aioble components over maintaining a growing custom BLE framework.
No dependencies are declared while this package remains a study.

BLE UART is a GATT service, not Bluetooth Classic SPP and not an automatically
created desktop COM port. The terminal must support NUS; a Classic-only serial
terminal will not work. Advertising makes the service discoverable; a client
must connect, subscribe to TX notifications, and write commands to RX.

## ESP32 compatibility

Espressif lists BLE for ESP32, S3, C2, C3, C5, C6, C61 and H2; firmware support
must be checked separately for each selected MicroPython image. S2 has no
Bluetooth radio; P4 has no integrated radio. A Python dependency cannot add a
missing controller or firmware driver. H2 also lacks Wi-Fi, which matters for
the rest of micrOS network boot independently of this transport.

First test from the board's MicroPython REPL, outside an active BLE session:

```python
import bluetooth
ble = bluetooth.BLE()
was_active = ble.active()
ble.active(True)
print(ble.active())
ble.active(was_active)
```

Success is only a controller smoke test, not verification of advertising or NUS.
MicroPython documents an ESP32 clock restriction below 80 MHz. Current micrOS
`Hooks._tune_performance()` selects at least 80 MHz for its listed targets;
verify the actual board clock and firmware. Test BLE alongside Wi-Fi and
ESP-NOW when enabled: heap usage, latency and reconnect behavior remain open.

## Shell integration

Existing integration points are `micrOS/source/Shell.py` and
`micrOS/source/Server.py:ShellCli`. Reuse Shell directly, without constructing a
socket client or duplicating its command interpreter.

Proposed public API (not available yet): `bluetooth load`, `bluetooth status`,
`bluetooth stop`, and `bluetooth help`. Import BLE and shell helpers lazily on
load. Start a managed task with `Common.micro_task`; no new config keys or
always-on imports are needed. A later boot hook can invoke load explicitly.

Data path:

```text
phone/PC NUS terminal -> RX writes -> bounded line buffer -> Shell.shell(line)
phone/PC NUS terminal <- TX notifications <- adapter.a_send(response)
```

Implementation contract:

- One active connection and a fresh Shell instance per session, retaining the
  existing `auth`/`appwd`, configuration mode, LM dispatch and hello behavior.
  Disconnect on a false return from `Shell.shell`, including failed auth.
- Handle `exit` in the transport, as ShellCli does. Send the initial prompt
  once notifications are enabled, or support an empty-line prompt request.
- Append a newline to output except for the prompt, matching ShellCli.a_send.
  Convert arbitrary shell response values to strings before UTF-8 encoding.
- BLE writes are fragments, not commands. Accumulate bytes until LF, CR or
  CRLF; handle split CRLF, multiple commands per write and split UTF-8. Decode
  only complete lines. Define empty lines as prompt requests explicitly.
- Set a finite command limit (initial proposal: 512 bytes), bounded queued
  input and an explicit overflow policy. Never execute a truncated command;
  discard through the next delimiter or close the session.
- Keep IRQ work small: capture state/data and signal the async worker. Do not
  run Shell, await, or perform slow command work inside BLE callbacks. Copy
  ephemeral IRQ data before retaining it. Bound buffers even while commands
  or notifications are pending; define overflow handling at every layer.
- Serialize command execution. Chunk encoded output into at most 20-byte
  notifications initially (default ATT MTU 23), with cooperative pacing and
  bounded handling of busy/error returns. Notifications lack application-level
  delivery acknowledgement; validate long help/config output on the target
  terminal. Larger MTUs are a later optimization.
- On disconnect discard pending input/output and shell state, then advertise
  again. Stop/cancellation must stop advertising, disconnect and release task
  resources. BLE is a singleton: do not overwrite another user's IRQ handler
  or replace registered services silently. Initial support should require
  exclusive controller ownership and document this constraint.

Shell authentication is application-level only: it does not encrypt BLE radio
traffic. Preserve the node's authentication policy and document that passwords
and commands need BLE encryption/pairing for confidentiality. Bonding and
persistent keys are a separate feature, not provided by this scaffold.

## NUS advertising and GATT

| Item | Value |
| --- | --- |
| Service UUID | `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` |
| RX: client writes | `6E400002-B5A3-F393-E0A9-E50E24DCCA9E` |
| TX: client subscribes | `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` |
| RX properties | Write and Write Without Response |
| TX properties | Notify |

Use connectable legacy advertising with flags and the complete 128-bit NUS
UUID. Put a bounded UTF-8 device name in scan response data to respect the
31-byte advertising limit. Initial interval proposal: 250 ms. Stop advertising
while connected to enforce one client, and restart after disconnect. Configure
the RX characteristic buffer explicitly; the default value buffer is 20 bytes.

## Package layout and naming

Implementation correction: MicroPython also treats the directory without an
`__init__.py` as a namespace package. The implemented shared `firmware()` loader
forces the native module using an empty `sys.path`; the naming advice below
alone does not prevent shadowing.

The requested registry name is `bluetooth`, also the name of MicroPython's
built-in module. Do not add `package/__init__.py` or import helpers as
`bluetooth.helper`: that could collide with the firmware module. Keep the
package-owned `/lib/bluetooth/pacman.json` receipt; a future `LM_bluetooth.py`
can contain the initial small adapter and import the firmware `bluetooth`
lazily. If helpers become necessary, use a distinct import namespace and
verify imports on-device. Current manifests contain only the PLCM receipt.

## Acceptance checks before calling this implemented

1. Mock transport tests: fragmentation, CR/LF framing, invalid UTF-8, overflow,
   notification chunking, disconnect during output and fresh session state.
2. Real Shell integration checks: hello, help, LM calls, configuration, correct
   and incorrect passwords, exit and reconnect without inherited auth.
3. Hardware on each supported ESP32 image: discover NUS, subscribe, execute
   commands, long output, burst input, repeat reconnect and stop/start.
4. Measure free heap and command latency with normal Wi-Fi/ESP-NOW traffic;
   check task cleanup and sustained runtime. Run the micrOS linter when runtime
   code is introduced. Host tests cannot prove radio behavior.

## Primary sources

- [MicroPython BLE API](https://docs.micropython.org/en/latest/library/bluetooth.html)
  — controller, GATT, IRQ lifetime, buffers, notification semantics, ESP32 clock.
- [MicroPython NUS peripheral example](https://github.com/micropython/micropython/blob/master/examples/bluetooth/ble_uart_peripheral.py)
  — dependency-free reference; its advertising helper is example code, not a
  required installable library. Do not expose its REPL instead of micrOS Shell.
- [aioble manifests](https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth)
  — component dependency definitions; pin versions when adopting dependencies.
- [Nordic NUS specification](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/libraries/bluetooth/services/nus.html)
  — service UUIDs and characteristic direction/properties.
- [Espressif chip overview](https://developer.espressif.com/esp-idf/)
  — hardware radio differences across ESP32 variants.
- [MicroPython ESP32 port](https://github.com/micropython/micropython/blob/master/ports/esp32/README.md)
  — port capabilities; use the exact installed release for implementation.

Online development documentation may differ from the firmware release used
by micrOS. No hardware validation was performed for this study.
