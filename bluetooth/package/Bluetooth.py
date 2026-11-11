"""Unified micrOS BLE NUS core: native backend, transport, Shell and lifecycle.

load() advertises cfgget("devfid"); stop()/status() control the same singleton
for Python callers and LM_bluetooth. Hardware and Shell imports stay lazy.
"""


SERVICE = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E'
RX = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E'
TX = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'
_TAG = 'bluetooth.shell'

_SERVER = None
_FIRMWARE = None


# Native backend and advertising


def firmware():
    """Force the native BLE module, bypassing the /lib/bluetooth namespace."""
    global _FIRMWARE
    if _FIRMWARE is None:
        import sys
        search_path = sys.path
        try:
            # MicroPython's empty-path import bypasses both filesystem modules
            # and a cached namespace with this name. No await while changed.
            sys.path = ()
            try:
                module = __import__('bluetooth')
            except ImportError:
                raise RuntimeError('Firmware has no Bluetooth support; use a BLE-enabled image')
        finally:
            sys.path = search_path
        if not hasattr(module, 'BLE') or not hasattr(module, 'UUID'):
            raise RuntimeError('Firmware has no bluetooth.BLE/UUID; use a BLE-enabled image')
        _FIRMWARE = module
    return _FIRMWARE


def payloads(name):
    bluetooth = firmware()
    encoded = name.encode('utf-8')
    if not encoded or len(encoded) > 29:
        raise ValueError('BLE name must be 1..29 UTF-8 bytes')
    advertisement = b'\x02\x01\x06\x11\x07' + bytes(bluetooth.UUID(SERVICE))
    scan = bytes((len(encoded) + 1, 9)) + encoded
    return advertisement, scan


# Line framing and Shell session


class Lines:
    """Incremental bounded UTF-8 line framing. Overflow closes the session."""
    def __init__(self):
        self.line = bytearray()
        self.after_cr = False

    def feed(self, value):
        if value == 10 and self.after_cr:
            self.after_cr = False
            return None
        self.after_cr = value == 13
        if value in (10, 13):
            result = bytes(self.line).decode('utf-8')
            self.line = bytearray()
            return result
        if len(self.line) >= 512:
            raise ValueError('Command exceeds 512 bytes')
        self.line.append(value)
        return None


def session_type():
    from Shell import Shell

    class BleShell(Shell):
        def __init__(self, server, generation):
            super().__init__()
            self.server = server
            self.generation = generation

        async def a_send(self, msg):
            text = str(msg)
            if text != self.prompt():
                text += '\n'
            await self.server.send(text.encode('utf-8'), self.generation)

    return BleShell


async def _run_shell(server):
    from Common import syslog
    generation = -1
    shell = None
    lines = None
    try:
        shell_type = session_type()
        while server.running:
            if server.conn is not None and not server.disconnecting:
                if generation != server.generation:
                    generation = server.generation
                    shell = shell_type(server, generation)
                    lines = Lines()
                try:
                    if server.overflow:
                        raise ValueError('BLE input buffer overflow')
                    # Swap without await: new IRQ input has its own bounded buffer.
                    incoming = server.pending
                    server.pending = bytearray()
                    for value in incoming:
                        if not server.alive(generation):
                            break
                        command = lines.feed(value)
                        if command is None:
                            continue
                        if command.strip() == 'exit':
                            await shell.a_send('Bye!')
                            if server.alive(generation):
                                server.disconnect()
                            break
                        if not await shell.shell(command):
                            if server.alive(generation):
                                server.disconnect()
                            break
                except Exception as error:
                    # Closing/replacing a session during a paced reply is normal.
                    if server.running and generation == server.generation:
                        syslog(f'[ERR] Bluetooth: {error}')
                        server.disconnect()
            else:
                shell = None
                lines = None
            await server.task.feed(sleep_ms=20)
    finally:
        server.close()


# GATT transport and connection ownership
class Peripheral:
    def __init__(self, name, start=True):
        bluetooth = firmware()
        self.ble = bluetooth.BLE()
        # BLE is singleton; never take over an already active controller.
        if self.ble.active():
            raise RuntimeError('BLE controller already active; exclusive ownership required')
        self.name = name
        self.started = False
        self.running = True
        self.closed = False
        self.disconnecting = False
        self.conn = None
        self.generation = 0
        self.pending = bytearray()
        self.overflow = False
        self.task = None
        self.advertising = False
        self.advertisement, self.scan = payloads(name)
        if start:
            self.start()

    def start(self):
        bluetooth = firmware()
        try:
            if self.task is not None:
                self.task.out = f'BLE activating radio: {self.name}'
            self.started = True
            self.ble.active(True)
            self.ble.gap_advertise(None)
            self.ble.config(gap_name=self.name)
            if self.task is not None:
                self.task.out = f'BLE registering NUS: {self.name}'
            ((self.tx, self.rx),) = self.ble.gatts_register_services(((
                bluetooth.UUID(SERVICE), (
                    (bluetooth.UUID(TX), 0x0010),
                    (bluetooth.UUID(RX), 0x0008 | 0x0004))),))
            self.ble.gatts_set_buffer(self.rx, 1025, True)
            self.ble.irq(self._irq)
            self._advertise()
        except Exception:
            self.close()
            raise

    def _advertise(self):
        if self.running and self.conn is None:
            self.advertising = False
            self.ble.gap_advertise(250000, adv_data=self.advertisement,
                                   resp_data=self.scan)
            self.advertising = True
            if self.task is not None:
                self.task.out = f'BLE advertising: {self.name}'

    def _irq(self, event, data):
        if not self.running:
            return
        if event == 1:  # central connect
            handle = data[0]
            if self.conn is not None:
                self.ble.gap_disconnect(handle)
                return
            # Discard characteristic bytes left by an earlier/rejected client.
            self.ble.gatts_read(self.rx)
            self.conn = handle
            self.disconnecting = False
            self.generation += 1
            self.pending = bytearray()
            self.overflow = False
            self.ble.gap_advertise(None)
            self.advertising = False
            if self.task is not None:
                self.task.out = f'BLE connected: {self.name}'
        elif event == 2 and data[0] == self.conn:
            self.conn = None
            self.generation += 1
            self.pending = bytearray()
            self.overflow = False
            try:
                self._advertise()
            except Exception as error:
                from Common import syslog
                syslog(f'[ERR] Bluetooth: {error}')
                if self.task is not None:
                    self.task.out = f'BLE error: {self.name}'
        elif event == 3 and data[0] == self.conn and data[1] == self.rx:
            value = self.ble.gatts_read(self.rx)
            if len(value) >= 1025 or len(self.pending) + len(value) > 1024:
                self.overflow = True
            elif not self.overflow:
                self.pending.extend(value)

    def alive(self, generation):
        return (self.running and not self.disconnecting and self.conn is not None
                and generation == self.generation)

    async def send(self, value, generation):
        for offset in range(0, len(value), 20):
            for attempt in range(5):
                if not self.alive(generation) or self.overflow:
                    raise OSError('BLE session closed or input overflow')
                try:
                    self.ble.gatts_notify(self.conn, self.tx, value[offset:offset + 20])
                    break
                except OSError:
                    if attempt == 4:
                        raise
                    await self.task.feed(sleep_ms=30)
            await self.task.feed(sleep_ms=15)

    async def run(self):
        await _run_shell(self)

    def disconnect(self):
        self.disconnecting = True
        self.ble.gap_disconnect(self.conn)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.running = False
        self.advertising = False
        if self.task is not None:
            self.task.out = f'BLE stopping: {self.name}'
        self.generation += 1
        self.pending = bytearray()
        if not self.started:
            if self.task is not None:
                self.task.out = f'BLE stopped: {self.name}'
            return
        try:
            self.ble.gap_advertise(None)
            if self.conn is not None:
                self.ble.gap_disconnect(self.conn)
        finally:
            self.conn = None
            self.ble.irq(None)
            self.ble.active(False)
            if self.task is not None:
                self.task.out = f'BLE stopped: {self.name}'


# Managed service lifecycle
async def _worker(server):
    from Common import micro_task, syslog
    try:
        try:
            with micro_task(_TAG) as task:
                server.task = task
                if not server.running:
                    return
                task.out = f'BLE starting: {server.name}'
                server.start()
                await server.run()
        finally:
            server.close()
    except Exception as error:
        syslog(f'[ERR] Bluetooth: {error}')
        if server.task is not None:
            server.task.out = f'BLE error: {server.name}'
        raise


def load():
    """Start NUS advertising. Requires exclusive ownership of the BLE radio."""
    global _SERVER
    from Common import micro_task, syslog
    from Config import cfgget
    previous = micro_task(_TAG)
    if _SERVER is not None and _SERVER.running:
        if previous is not None and not previous.done.is_set():
            if _SERVER.started and _SERVER.conn is None and not _SERVER.advertising:
                try:
                    _SERVER._advertise()
                except Exception as error:
                    syslog(f'[ERR] Bluetooth: {error}')
                    raise
            return status()
        # A killed task may not have entered its coroutine/finally block yet.
        _SERVER.close()
    if previous is not None and not previous.done.is_set():
        raise RuntimeError('Previous Bluetooth task is stopping; retry shortly')
    server = None
    coroutine = None
    try:
        server = Peripheral(cfgget('devfid'), start=False)
        coroutine = _worker(server)
        if not micro_task(_TAG, task=coroutine):
            raise RuntimeError('Cannot start Bluetooth task')
        server.task = micro_task(_TAG)
        if server.task is not None:
            server.task.out = f'BLE starting: {server.name}'
    except Exception as error:
        syslog(f'[ERR] Bluetooth: {error}')
        if coroutine is not None:
            coroutine.close()
        if server is not None:
            server.close()
        raise
    _SERVER = server
    return status()


def stop():
    """Disconnect and stop advertising; worker exits cooperatively."""
    if _SERVER is not None and _SERVER.running:
        try:
            _SERVER.close()
        except Exception as error:
            from Common import syslog
            syslog(f'[ERR] Bluetooth: {error}')
            raise
    return status()


def status():
    """Listener flags and the managed task output; errors go to Common.syslog."""
    return {'active': _SERVER is not None and _SERVER.running,
            'connected': _SERVER is not None and _SERVER.conn is not None,
            'state': 'stopped' if _SERVER is None or _SERVER.task is None else _SERVER.task.out,
            'advertising': _SERVER is not None and _SERVER.advertising}
