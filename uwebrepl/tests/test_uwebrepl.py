"""Host checks for the LM with the real micrOS password decorator."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1] / 'source'


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lm(monkeypatch):
    config = ModuleType('Config')
    config.cfgget = lambda key: 'test-pass' if key == 'appwd' else None
    common = ModuleType('Common')
    common.web_endpoint = Mock(return_value=True)
    types = ModuleType('Types')
    types.resolve = lambda commands, widgets=False: commands
    for module in (config, common, types):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    auth = import_file('Auth', SOURCE / 'Auth.py')
    monkeypatch.setitem(sys.modules, 'Auth', auth)
    backend = ModuleType('webrepl')
    backend.listen_s = None
    backend.start = Mock()
    backend.stop = Mock()
    monkeypatch.setitem(sys.modules, 'webrepl', backend)
    select = ModuleType('select')
    select.POLLIN = 1

    class Poll:
        def register(self, sock, mask):
            assert mask == 1  # Never request POLLOUT on a listening socket.
            self.sock = sock

        def poll(self, timeout):
            assert timeout == 0  # Status must not block the micrOS event loop.
            return [(self.sock, self.sock.events)] if self.sock.events else []

    select.poll = Poll
    monkeypatch.setitem(sys.modules, 'select', select)
    module = import_file('LM_uwebrepl', ROOT / 'package' / 'LM_uwebrepl.py')
    return module, backend, common, auth


class Listener:
    """MicroPython stream-style socket: deliberately no getsockname/fileno."""
    def __init__(self, closed=False, events=0):
        self.events = 32 if closed else events  # MP_STREAM_POLL_NVAL


def listener(port=None, closed=False):
    sock = Listener(closed=closed)
    if port is not None:
        # Optional extension on ports that expose their bound address.
        sock.getsockname = lambda: ('0.0.0.0', port)
    return sock


def test_loading_only_registers_routes(lm, monkeypatch):
    module, backend, common, _ = lm
    monkeypatch.setitem(sys.modules, 'webrepl', None)
    assert '/uwebrepl' in module.load()
    assert [call.args for call in common.web_endpoint.call_args_list] == [
        ('uwebrepl', 'uwebrepl/index.html'),
        ('uwebrepl/status', module._status_get),
        ('uwebrepl/enable', module._enable_post, 'POST'),
    ]
    backend.start.assert_not_called()


def test_initial_state_does_not_start_listener(lm):
    module, backend, _, _ = lm
    assert module.status() == {'available': True, 'active': False, 'port': 8266}
    backend.start.assert_not_called()


def test_external_listener_and_custom_port(lm):
    module, backend, _, _ = lm
    backend.listen_s = listener(9000)
    assert module.enable(pwd='test-pass') == {'available': True, 'active': True, 'port': 9000}
    backend.start.assert_not_called()


def test_upstream_stop_leaves_closed_socket(lm):
    module, backend, _, _ = lm
    backend.listen_s = listener(closed=True)
    assert module.status()['active'] is False


@pytest.mark.parametrize('events, active', [(0, True), (1, True), (8, False),
                                           (16, False), (32, False), (33, False)])
def test_micropython_socket_without_cpython_methods(lm, events, active):
    module, backend, _, _ = lm
    backend.listen_s = Listener(events=events)
    assert not hasattr(backend.listen_s, 'getsockname')
    assert module.status() == {'available': True, 'active': active, 'port': 8266}


@pytest.mark.parametrize('error', [OSError('closed'), ValueError('negative fd')])
def test_poll_failure_reports_inactive(lm, monkeypatch, error):
    module, backend, _, _ = lm
    backend.listen_s = listener()
    monkeypatch.setattr(sys.modules['select'], 'poll', Mock(side_effect=error))
    assert module.status()['active'] is False


@pytest.mark.parametrize('name', ['enable', 'disable', '_enable_post'])
@pytest.mark.parametrize('password', [None, 'wrong'])
def test_mutations_require_real_auth(lm, name, password):
    module, backend, _, auth = lm
    with pytest.raises(auth.AuthRequired):
        getattr(module, name)(pwd=password)
    backend.start.assert_not_called()
    backend.stop.assert_not_called()


def test_enable_uses_app_password_and_does_not_restart(lm):
    module, backend, _, _ = lm
    backend.start.side_effect = lambda **_: setattr(backend, 'listen_s', listener())
    assert module.enable(pwd='test-pass')['active']
    assert module.enable(pwd='test-pass')['active']
    backend.start.assert_called_once_with(password='test-pass')
    assert 'test-pass' not in str(module.status())


def test_disable_reads_closed_state(lm):
    module, backend, _, _ = lm
    backend.listen_s = listener()
    backend.stop.side_effect = lambda: setattr(backend, 'listen_s', listener(closed=True))
    assert module.disable(pwd='test-pass')['active'] is False


def test_unavailable_firmware(lm, monkeypatch):
    module, _, _, _ = lm
    monkeypatch.setitem(sys.modules, 'webrepl', None)
    assert module.status()['available'] is False
    kind, data = module._enable_post({}, b'', pwd='test-pass')
    assert kind == 'application/json'
    assert 'unavailable' in data['error']


def test_simulator_stub_is_not_reported_active(lm):
    module, backend, _, _ = lm
    del backend.listen_s
    assert module.status()['available'] is False


def test_start_failure_closes_partial_listener(lm):
    module, backend, _, _ = lm
    backend.start.side_effect = OSError('port in use')
    _, data = module._enable_post({}, b'', pwd='test-pass')
    assert data == {'error': 'port in use'}
    backend.stop.assert_called_once()


def test_successful_http_enable_and_status(lm):
    module, backend, _, _ = lm
    backend.start.side_effect = lambda **_: setattr(backend, 'listen_s', listener())
    assert module._enable_post({}, b'', pwd='test-pass')[1]['active']
    assert module._status_get({}, b'')[1]['active']
