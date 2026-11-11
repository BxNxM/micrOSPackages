"""Exercise the BLE transport with real Shell.py and a fake controller."""
import asyncio
import importlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1] / 'source'


def read_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Radio:
    def __init__(self):
        self.enabled = False
        self.handler = None
        self.output = []
        self.value = b''
        self.adverts = []
        self.busy = 0

    def active(self, value=None):
        if value is not None:
            self.enabled = value
        return self.enabled

    def gap_advertise(self, interval, **kwargs):
        self.adverts.append((interval, kwargs))

    def config(self, **kwargs):
        pass

    def gatts_register_services(self, services):
        return ((10, 11),)

    def gatts_set_buffer(self, *args):
        pass

    def irq(self, handler):
        self.handler = handler

    def gatts_read(self, _handle):
        value, self.value = self.value, b''
        return value

    def gatts_notify(self, conn, handle, value):
        if self.busy:
            self.busy -= 1
            raise OSError('busy')
        self.output.append(bytes(value))

    def gap_disconnect(self, conn):
        if self.handler:
            self.handler(2, (conn, 0, b''))

    def connect(self, conn=1):
        self.handler(1, (conn, 0, b''))

    def write(self, value, conn=1):
        self.value = value
        self.handler(3, (conn, 11))

    def text(self):
        return b''.join(self.output).decode()


class TaskProbe:
    """Managed task surface used by transport tests outside the worker."""
    def __init__(self):
        self.out = ''
        self.delays = []

    async def feed(self, sleep_ms=1):
        self.delays.append(sleep_ms)
        await asyncio.sleep(0)


def peripheral(lm, name='test'):
    server = lm.Peripheral(name)
    server.task = TaskProbe()
    return server


@pytest.fixture
def env(monkeypatch):
    config = {'devfid': 'test', 'auth': True, 'appwd': 'secret', 'hwuid': '123'}
    logs = []
    def module(name, **values):
        result = ModuleType(name)
        result.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, result)
        return result
    module('Config', cfgget=lambda key=None: config if key is None else config.get(key),
           cfgput=lambda key, value, **kw: config.update({key: value}) or True)
    module('machine', reset=lambda: None, soft_reset=lambda: None)
    module('Files', OSPath=type('OSPath', (), {'MODULES': '/modules'}),
           ilist_fs=lambda **kw: [], path_join=lambda *p: '/'.join(p))
    module('Tasks', lm_exec=lambda arg_list: (True, ' '.join(arg_list)))
    module('Debug', syslog=logs.append)
    module('Common', syslog=logs.append)
    shell = read_module('Shell', SOURCE / 'Shell.py')
    monkeypatch.setitem(sys.modules, 'Shell', shell)
    radio = Radio()
    module('bluetooth', BLE=lambda: radio,
           UUID=lambda value: bytes.fromhex(value.replace('-', ''))[::-1])
    for name in tuple(sys.modules):
        if name == 'Bluetooth':
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.syspath_prepend(str(ROOT / 'package'))
    lm = importlib.import_module('Bluetooth')
    lm._test_logs = logs
    return lm, radio, config


def framed(lm, chunks):
    lines = lm.Lines()
    result = []
    for chunk in chunks:
        for value in chunk:
            line = lines.feed(value)
            if line is not None:
                result.append(line)
    return result


def test_fragmented_lines_and_utf8(env):
    lm, _, _ = env
    assert framed(lm, [b'hel', b'lo\r', b'\nversion\n', b'\xc3', b'\xa9\r\n\n']) == [
        'hello', 'version', 'é', '']
    assert framed(lm, [b'x' * 512 + b'\n']) == ['x' * 512]


@pytest.mark.parametrize('value', [b'x' * 513 + b'\n', b'\xff\n'])
def test_invalid_lines_rejected(env, value):
    with pytest.raises((ValueError, UnicodeError)):
        framed(env[0], [value])


def test_advertising_and_ownership(env):
    lm, radio, _ = env
    server = peripheral(lm, 'micrOS')
    interval, payload = radio.adverts[-1]
    assert interval == 250000
    assert len(payload['adv_data']) <= 31
    assert len(payload['resp_data']) <= 31
    with pytest.raises(RuntimeError, match='already active'):
        lm.Peripheral('other')
    server.close()
    server.close()
    assert not radio.enabled


@pytest.mark.parametrize('name', ['', 'x' * 30, 'é' * 15])
def test_name_limit(env, name):
    with pytest.raises(ValueError):
        env[0].Peripheral(name)
    assert not env[1].enabled


async def turns(count=150):
    for _ in range(count):
        await asyncio.sleep(0)


def test_real_shell_sessions(env):
    lm, radio, _ = env
    async def scenario():
        server = peripheral(lm)
        worker = asyncio.create_task(server.run())
        radio.connect()
        radio.write(b'\nhello\nsecret\nversion\nconf\ndevfid\nnoconf\nhelp\n')
        await turns(400)
        output = radio.text()
        assert '[password] test $ ' in output
        assert 'hello:test:123:' in output
        assert 'AuthOk\n' in output
        assert '[configure] test $ ' in output
        assert '[MICROS]' in output
        assert all(len(chunk) <= 20 for chunk in radio.output)
        radio.write(b'exit\nversion\n')
        await turns()
        assert server.conn is None
        assert radio.text().endswith('Bye!\n')
        assert radio.adverts[-1][0] == 250000
        radio.output.clear()
        radio.connect()  # Same handle, new shell/auth state.
        radio.write(b'version\n')
        await turns()
        assert 'AuthFailed' in radio.text()
        assert server.conn is None
        server.close()
        await worker
    asyncio.run(scenario())


@pytest.mark.parametrize('payload', [b'x' * 1025, b'x' * 513 + b'\n', b'\xff\n'])
def test_overflow_and_bad_encoding_disconnect(env, payload):
    lm, radio, _ = env
    async def scenario():
        server = peripheral(lm)
        worker = asyncio.create_task(server.run())
        radio.connect()
        radio.write(payload)
        await turns()
        assert server.conn is None
        assert len(lm._test_logs) == 1
        assert lm._test_logs[0].startswith('[ERR] Bluetooth: ')
        expected = ('overflow' if len(payload) > 1024 else
                    'Command exceeds 512 bytes' if len(payload) > 512 else 'utf-8')
        assert expected in lm._test_logs[0]
        assert not hasattr(server, 'error')
        assert server.advertising
        assert server.task.out == 'BLE advertising: test'
        assert 'AuthOk' not in radio.text()
        radio.connect()
        assert server.task.out == 'BLE connected: test'
        server.close()
        await worker
    asyncio.run(scenario())


def test_send_retry_and_stale_generation(env):
    lm, radio, _ = env
    async def scenario():
        server = peripheral(lm)
        radio.connect()
        generation = server.generation
        radio.busy = 2
        await server.send(b'abc' * 20, generation)
        assert b''.join(radio.output) == b'abc' * 20
        assert server.task.delays == [30, 30, 15, 15, 15]
        radio.gap_disconnect(1)
        radio.connect()
        with pytest.raises(OSError):
            await server.send(b'old secret', generation)
        radio.busy = 5
        with pytest.raises(OSError):
            await server.send(b'busy', server.generation)
        server.close()
    asyncio.run(scenario())


def test_cancel_releases_radio(env):
    lm, radio, _ = env
    async def scenario():
        server = peripheral(lm)
        worker = asyncio.create_task(server.run())
        await turns(1)
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker
        assert not radio.enabled
        assert radio.handler is None
    asyncio.run(scenario())


def test_managed_load_stop_restart(env, monkeypatch):
    lm, radio, config = env
    tasks = {}
    class Managed(TaskProbe):
        def __init__(self, coroutine):
            super().__init__()
            self.done = asyncio.Event()
            self.task = asyncio.create_task(coroutine)
        def __enter__(self):
            return self
        def __exit__(self, *_):
            self.done.set()
    def micro_task(tag, task=None):
        if task is not None:
            tasks[tag] = Managed(task)
            return {tag: 'Started'}
        return tasks.get(tag)
    common = ModuleType('Common')
    common.micro_task = micro_task
    common.syslog = lm._test_logs.append
    monkeypatch.setitem(sys.modules, 'Common', common)
    original_active = radio.active
    starting_output = []
    def active(value=None):
        if value is True:
            starting_output.append(tasks[lm._TAG].out)
        return original_active(value)
    monkeypatch.setattr(radio, 'active', active)
    async def scenario():
        assert lm.load() == {'active': True, 'connected': False,
                             'state': 'BLE starting: test', 'advertising': False}
        task = tasks[lm._TAG]
        assert lm.status()['state'] == task.out
        assert 'starting' in task.out.lower()
        assert lm._SERVER.name == config['devfid']
        assert lm.load()['active']
        await turns(1)
        assert starting_output and 'activating radio' in starting_output[0].lower()
        assert lm.status()['state'] == task.out == 'BLE advertising: test'
        assert lm.status()['advertising']
        assert 'advertising' in task.out.lower()
        assert 20 in task.delays
        radio.connect()
        assert lm.status()['state'] == task.out == 'BLE connected: test'
        assert not lm.status()['advertising']
        assert 'connected' in task.out.lower()
        radio.write(b'\nsecret\nversion\n')
        await turns(100)
        assert 'AuthOk' in radio.text()
        assert all(value not in task.out for value in ('secret', 'version', 'AuthOk'))
        radio.gap_disconnect(1)
        assert lm.status()['advertising']
        assert lm.status()['state'] == task.out == 'BLE advertising: test'
        assert 'advertising' in task.out.lower()
        assert not lm.stop()['active']
        assert not lm.status()['advertising']
        assert lm.status()['state'] == task.out == 'BLE stopped: test'
        assert 'stopped' in task.out.lower()
        task.out = 'Retained Bluetooth diagnostics'
        assert lm.status()['state'] == task.out
        with pytest.raises(RuntimeError, match='stopping'):
            lm.load()
        await tasks[lm._TAG].task
        config['devfid'] = 'TinyDevBoard'
        assert lm.load()['active']
        assert lm._SERVER.name == config['devfid']
        await turns(1)
        assert radio.adverts[-1][1]['resp_data'].endswith(b'TinyDevBoard')
        lm.stop()
        await tasks[lm._TAG].task
        assert not radio.enabled
        assert lm._test_logs == []
    asyncio.run(scenario())


def test_disconnect_during_notification_does_not_leak(env, monkeypatch):
    lm, radio, _ = env
    original = radio.gatts_notify
    def drop(conn, handle, value):
        original(conn, handle, value)
        radio.gap_disconnect(conn)
        radio.connect(conn)
    monkeypatch.setattr(radio, 'gatts_notify', drop)
    async def scenario():
        server = peripheral(lm)
        radio.connect()
        with pytest.raises(OSError):
            await server.send(b'secret output' * 10, server.generation)
        assert len(radio.output) == 1
        server.close()
    asyncio.run(scenario())


def test_exit_does_not_disconnect_replacement_connection(env, monkeypatch):
    lm, radio, _ = env
    original = radio.gatts_notify
    def reconnect(conn, handle, value):
        original(conn, handle, value)
        if value == b'Bye!\n':
            radio.gap_disconnect(conn)
            radio.connect(2)
    monkeypatch.setattr(radio, 'gatts_notify', reconnect)
    async def scenario():
        server = peripheral(lm)
        worker = asyncio.create_task(server.run())
        try:
            radio.connect()
            radio.write(b'exit\n')
            await turns()
            assert server.conn == 2
            radio.write(b'\n', conn=2)
            await turns()
            assert radio.text().endswith('[password] test $ ')
        finally:
            server.close()
            await worker
    asyncio.run(scenario())


def test_stop_during_paced_reply_keeps_stopped_state(env):
    lm, radio, config = env
    config['auth'] = False
    async def scenario():
        server = peripheral(lm)
        class StopDuringReply(TaskProbe):
            async def feed(self, sleep_ms=1):
                if sleep_ms == 15:
                    server.close()
                await super().feed(sleep_ms)
        server.task = StopDuringReply()
        worker = asyncio.create_task(server.run())
        radio.connect()
        radio.write(b'help\n')
        await worker
        assert 15 in server.task.delays
        assert radio.text() == '[MICROS]\n'
        assert not radio.enabled
        assert server.task.out == 'BLE stopped: test'
        assert lm._test_logs == []
        assert 'stopped' in server.task.out.lower()
    asyncio.run(scenario())


def test_reconnect_during_reply_keeps_new_session_healthy(env, monkeypatch):
    lm, radio, config = env
    config['auth'] = False
    original = radio.gatts_notify
    dropped = False
    def reconnect(conn, handle, value):
        nonlocal dropped
        original(conn, handle, value)
        if not dropped:
            dropped = True
            radio.gap_disconnect(conn)
            radio.connect(2)
    monkeypatch.setattr(radio, 'gatts_notify', reconnect)
    async def scenario():
        server = peripheral(lm)
        worker = asyncio.create_task(server.run())
        try:
            radio.connect()
            radio.write(b'help\n')
            await turns()
            assert dropped and server.conn == 2
            assert lm._test_logs == []
            assert server.task.out == 'BLE connected: test'
            radio.output.clear()
            radio.write(b'version\n', conn=2)
            await turns()
            assert radio.text() == sys.modules['Shell'].Shell.MICROS_VERSION + '\ntest $ '
            assert lm._test_logs == []
        finally:
            server.close()
            await worker
    asyncio.run(scenario())


def test_macos_tester_framing_and_disconnect(monkeypatch):
    tester = read_module('ble_shell_tester', ROOT / 'helpers/ble_shell.py')
    async def scenario():
        writes = []
        disconnected = asyncio.Event()
        class Client:
            async def write_gatt_char(self, uuid, value, response):
                assert response and uuid == tester.RX
                writes.append(value)
                if value.endswith(b'\n'):
                    terminal.notify(None, b'\xc3')
                    terminal.notify(None, b'\xa9\ntest $ ')
        terminal = tester.Terminal(Client(), disconnected, 0.1)
        assert await terminal.command('x' * 45) == 'é\ntest $ '
        assert b''.join(writes) == b'x' * 45 + b'\n'
        assert all(len(value) <= 20 for value in writes)
        with pytest.raises(ValueError):
            await terminal.command('x' * 513)
        with pytest.raises(ValueError):
            await terminal.command('hello\nversion')
        class Drop:
            async def write_gatt_char(self, *_args, **_kwargs):
                disconnected.set()
                terminal.changed.set()
        terminal.client = Drop()
        with pytest.raises(ConnectionError):
            await terminal.command('hello')
    asyncio.run(scenario())


@pytest.mark.parametrize('password', ['secret', 'wrong'])
def test_tester_end_to_end_with_real_shell(env, monkeypatch, password):
    """Connect the actual host tester to the actual wrapper through fake BLE."""
    from argparse import Namespace
    lm, radio, _ = env
    tester = read_module('ble_shell_e2e', ROOT / 'helpers/ble_shell.py')
    monkeypatch.setattr(tester.getpass, 'getpass', lambda _: password)
    class Device:
        address = 'macos-device-uuid'
        name = 'test'
    class Advertisement:
        local_name = 'test'
    class Scanner:
        @staticmethod
        async def discover(**_kwargs):
            return {'test': (Device(), Advertisement())}
    class Client:
        def __init__(self, device, disconnected_callback):
            self.disconnected_callback = disconnected_callback
            self.is_connected = False
            self.notify = None
        async def __aenter__(self):
            self.is_connected = True
            radio.connect()
            original_notify = radio.gatts_notify
            original_disconnect = radio.gap_disconnect
            def notify(conn, handle, value):
                original_notify(conn, handle, value)
                if self.notify:
                    self.notify(None, value)
            def disconnect(conn):
                original_disconnect(conn)
                self.is_connected = False
                self.disconnected_callback(self)
            radio.gatts_notify = notify
            radio.gap_disconnect = disconnect
            return self
        async def __aexit__(self, *_args):
            if self.is_connected:
                radio.gap_disconnect(1)
        async def start_notify(self, _uuid, callback):
            self.notify = callback
        async def write_gatt_char(self, _uuid, value, response):
            radio.write(value)
            await asyncio.sleep(0)
    bleak = ModuleType('bleak')
    bleak.BleakClient, bleak.BleakScanner = Client, Scanner
    monkeypatch.setitem(sys.modules, 'bleak', bleak)
    async def scenario():
        server = peripheral(lm)
        worker = asyncio.create_task(server.run())
        args = Namespace(scan_timeout=1, scan=False, name='test', address=None,
                         timeout=1, test=True, command=[])
        try:
            if password == 'secret':
                await tester.run(args)
            else:
                with pytest.raises((ConnectionError, RuntimeError)):
                    await tester.run(args)
        finally:
            server.close()
            await worker
    asyncio.run(scenario())


@pytest.mark.parametrize('action', ['stop', 'kill'])
def test_stop_or_kill_before_first_task_step(env, monkeypatch, action):
    lm, radio, _ = env
    tasks = {}
    class Managed(TaskProbe):
        def __init__(self, callback):
            super().__init__()
            self.done = asyncio.Event()
            self.task = asyncio.create_task(callback)
        def __enter__(self):
            return self
        def __exit__(self, *_):
            self.done.set()
    def micro_task(tag, task=None):
        if task is not None:
            tasks[tag] = Managed(task)
            return {tag: 'Starting'}
        return tasks.get(tag)
    common = ModuleType('Common')
    common.micro_task = micro_task
    common.syslog = lm._test_logs.append
    monkeypatch.setitem(sys.modules, 'Common', common)
    async def scenario():
        lm.load()
        old = tasks[lm._TAG]
        assert not radio.enabled
        if action == 'stop':
            lm.stop()
            await old.task
        else:
            # Real TaskBase.cancel removes its registration immediately.
            old.task.cancel()
            del tasks[lm._TAG]
            with pytest.raises(asyncio.CancelledError):
                await old.task
        assert not radio.enabled
        lm.load()
        await turns(2)
        assert radio.enabled
        lm.stop()
        await tasks[lm._TAG].task
        assert not radio.enabled
    asyncio.run(scenario())


def test_start_failure_releases_controller(env, monkeypatch):
    lm, radio, _ = env
    def fail(*_args):
        raise OSError('Cannot register NUS')
    monkeypatch.setattr(radio, 'gatts_register_services', fail)
    with pytest.raises(OSError, match='Cannot register'):
        lm.Peripheral('test')
    assert not radio.enabled
    assert radio.handler is None
    assert lm._test_logs == []


@pytest.mark.parametrize('stage', ['register', 'advertise', 'shell'])
def test_managed_start_failure_logs_error_and_sets_task_state(env, monkeypatch, stage):
    """A failed async startup must explain why scanning cannot find the board."""
    lm, radio, _ = env
    tasks = {}
    class Managed(TaskProbe):
        def __init__(self, coroutine):
            super().__init__()
            self.done = asyncio.Event()
            self.task = asyncio.create_task(coroutine)
        def __enter__(self):
            return self
        def __exit__(self, *_):
            self.done.set()
    def micro_task(tag, task=None):
        if task is not None:
            tasks[tag] = Managed(task)
            return {tag: 'Starting'}
        return tasks.get(tag)
    common = ModuleType('Common')
    common.micro_task = micro_task
    common.syslog = lm._test_logs.append
    monkeypatch.setitem(sys.modules, 'Common', common)
    detail = {'register': 'Cannot register NUS', 'advertise': 'Cannot advertise NUS',
              'shell': 'Shell unavailable'}[stage]
    def fail(*_args, **_kwargs):
        raise OSError(detail)
    if stage == 'register':
        monkeypatch.setattr(radio, 'gatts_register_services', fail)
    elif stage == 'advertise':
        advertise = radio.gap_advertise
        def fail_advertise(interval, **kwargs):
            return advertise(interval, **kwargs) if interval is None else fail()
        monkeypatch.setattr(radio, 'gap_advertise', fail_advertise)
    else:
        monkeypatch.setattr(lm, 'session_type', fail)
    async def scenario():
        lm.load()
        task = tasks[lm._TAG]
        with pytest.raises(OSError, match=detail):
            await task.task
        state = lm.status()
        assert not state['active'] and not state['advertising']
        assert 'last_error' not in state
        assert state['state'] == task.out == 'BLE error: test'
        assert lm._test_logs == [f'[ERR] Bluetooth: {detail}']
        assert task.done.is_set()
        assert not radio.enabled and radio.handler is None
    asyncio.run(scenario())


def test_shell_initialization_failure_is_reported(env, monkeypatch):
    lm, radio, _ = env
    def fail():
        raise ImportError('Shell unavailable')
    monkeypatch.setattr(lm, 'session_type', fail)
    async def scenario():
        server = peripheral(lm)
        with pytest.raises(ImportError):
            await server.run()
        assert not hasattr(server, 'error')
        assert not radio.enabled
        assert lm._test_logs == []
    asyncio.run(scenario())


@pytest.mark.parametrize('failure', ['native', 'schedule'])
def test_load_failure_logs_once(env, monkeypatch, failure):
    lm, radio, _ = env
    common = sys.modules['Common']
    monkeypatch.setattr(common, 'micro_task', lambda _tag, task=None: None, raising=False)
    if failure == 'native':
        def unavailable():
            raise RuntimeError('Firmware has no Bluetooth support')
        monkeypatch.setattr(lm, 'firmware', unavailable)
        detail = 'Firmware has no Bluetooth support'
    else:
        detail = 'Cannot start Bluetooth task'
    with pytest.raises(RuntimeError, match=detail):
        lm.load()
    assert lm._test_logs == [f'[ERR] Bluetooth: {detail}']
    assert not radio.enabled
    assert lm.status() == {'active': False, 'connected': False,
                           'state': 'stopped', 'advertising': False}


def test_irq_advertising_failure_logs_once(env, monkeypatch):
    lm, radio, _ = env
    server = peripheral(lm)
    radio.connect()
    advertise = radio.gap_advertise
    def fail(interval, **kwargs):
        if interval is not None:
            raise OSError('Advertising restart failed')
        return advertise(interval, **kwargs)
    monkeypatch.setattr(radio, 'gap_advertise', fail)
    try:
        radio.gap_disconnect(1)
        assert server.conn is None and not server.advertising
        assert server.task.out == 'BLE error: test'
        assert lm._test_logs == ['[ERR] Bluetooth: Advertising restart failed']
        monkeypatch.setattr(radio, 'gap_advertise', advertise)
        monkeypatch.setattr(lm, '_SERVER', server)
        server.task.done = asyncio.Event()
        monkeypatch.setattr(sys.modules['Common'], 'micro_task',
                            lambda tag: server.task, raising=False)
        assert lm.load()['advertising']
        assert lm._SERVER is server
        assert server.task.out == 'BLE advertising: test'
    finally:
        server.close()


def test_tester_timeout(env):
    tester = read_module('ble_shell_timeout', ROOT / 'helpers/ble_shell.py')
    class SilentClient:
        async def write_gatt_char(self, *_args, **_kwargs):
            pass
    async def scenario():
        terminal = tester.Terminal(SilentClient(), asyncio.Event(), 0.001)
        with pytest.raises(asyncio.TimeoutError):
            await terminal.command('hello')
    asyncio.run(scenario())


def test_new_connection_discards_stale_characteristic_bytes(env):
    lm, radio, _ = env
    server = peripheral(lm)
    radio.value = b'secret\n'
    radio.connect()
    assert radio.value == b''
    assert not server.pending
    server.close()


def test_installed_layout_and_lazy_public_entrypoint(env, monkeypatch, tmp_path):
    """Import through the generated mip layout, without the source import path."""
    import json
    from shutil import copyfile
    from unittest.mock import Mock
    lib = tmp_path / 'lib'
    manifest = json.loads((ROOT / 'package.json').read_text())
    for destination, source in manifest['urls']:
        relative = source.split('/package/', 1)[1]
        target = lib / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(ROOT / 'package' / relative, target)
    assert not (lib / 'bluetooth/__init__.py').exists()
    assert not any('helpers/' in dest or 'tests/' in dest for dest, _ in manifest['urls'])
    for name in tuple(sys.modules):
        if name == 'Bluetooth':
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, 'path', [p for p in sys.path if p != str(ROOT / 'package')])
    monkeypatch.setattr(sys.modules['Files'].OSPath, 'LIB', str(lib), raising=False)
    firmware = sys.modules['bluetooth']
    lm = read_module('LM_bluetooth_installed', lib / 'LM_bluetooth.py')
    assert lm.status() == {'active': False, 'connected': False,
                           'state': 'stopped', 'advertising': False}
    assert lm.stop() == lm.status()
    assert 'micros_ble' not in sys.modules
    assert 'Bluetooth' not in sys.modules
    backend = lm._backend()
    assert Path(backend.__file__).is_relative_to(lib)
    assert sys.modules['bluetooth'] is firmware
    assert not env[1].enabled
    assert str(lib / 'bluetooth') in sys.path
    assert lm._backend() is backend
    assert backend is importlib.import_module('Bluetooth')
    assert not (lib / 'bluetooth/micros_ble').exists()
    assert {dest for dest, _ in manifest['urls']} == {
        'LM_bluetooth.py', 'bluetooth/Bluetooth.py', 'bluetooth/pacman.json'}
    backend.load = Mock(return_value={'active': True})
    backend.stop = Mock(return_value={'active': False})
    assert lm.load() == {'active': True}
    backend.load.assert_called_once_with()
    assert lm.stop() == {'active': False}


def test_connection_and_advertising_use_native_despite_shadow(env, monkeypatch):
    import builtins
    lm, radio, _ = env
    native = sys.modules['bluetooth']
    namespace = ModuleType('bluetooth')
    namespace.__path__ = ['/lib/bluetooth']
    original_import = builtins.__import__
    original_path = sys.path
    def micropython_import(name, *args, **kwargs):
        if name == 'bluetooth':
            return native if not sys.path else namespace
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', micropython_import)
    server = peripheral(lm, 'TinyDevBoard')
    assert radio.enabled
    assert server.ble is radio
    assert sys.path is original_path
    assert radio.adverts[-1][0] == 250000
    server.close()


def test_frontend_discovers_core_started_by_another_caller(env, monkeypatch):
    from types import SimpleNamespace
    core, _, _ = env
    task = TaskProbe()
    task.out = 'BLE connected: test'
    server = SimpleNamespace(running=True, conn=7,
                             task=task, advertising=False)
    def close():
        server.running = False
        server.conn = None
        task.out = 'BLE stopped: test'
    server.close = close
    monkeypatch.setattr(core, '_SERVER', server)
    frontend = read_module('LM_bluetooth_core_first', ROOT / 'package/LM_bluetooth.py')
    assert frontend._BACKEND is None
    assert frontend.status() == core.status() == {
        'active': True, 'connected': True,
        'state': task.out, 'advertising': False}
    assert frontend.stop() == core.status() == {
        'active': False, 'connected': False,
        'state': task.out, 'advertising': False}
