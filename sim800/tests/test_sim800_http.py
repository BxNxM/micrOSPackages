"""
LM_sim800_http.py unit tests

Run:
  cd sim800
  python3 -m pytest tests/test_sim800_http.py -v
"""

import unittest
import sys
import types
import importlib.util
from unittest import mock
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "package"


def _install_stubs():
    if "machine" not in sys.modules:
        m = types.ModuleType("machine")

        class FakePin:
            IN = 0; OUT = 1; PULL_UP = 2; PULL_DOWN = 3
            def __init__(self, *a, **kw): pass

        class FakeUART:
            def __init__(self, *a, **kw): self._buf = b""
            def write(self, data): pass
            def read(self, *a): return self._buf or None
            def any(self): return len(self._buf)

        m.Pin = FakePin
        m.UART = FakeUART
        m.WDT = type("WDT", (), {"__init__": lambda s, **kw: None, "feed": lambda s: None})
        sys.modules["machine"] = m

    for mod_name in ("Common", "Config", "microIO", "Types"):
        if mod_name not in sys.modules:
            stub = types.ModuleType(mod_name)
            if mod_name == "Common":
                stub.console = lambda *a, **kw: None
                stub.micro_task = mock.MagicMock()
                stub.exec_cmd = mock.MagicMock(return_value=(True, "{}"))

                class FakeTaskCtx:
                    async def feed(self, sleep_ms=0): pass
                    def __enter__(self): return self
                    def __exit__(self, *a): pass

                def _micro_task_side_effect(tag=None, task=None, _wrap=False):
                    if task is not None:
                        if hasattr(task, 'close'):
                            task.close()
                        return {'tag': tag, 'state': 'created'}
                    return FakeTaskCtx()

                stub.micro_task = mock.MagicMock(side_effect=_micro_task_side_effect)
            elif mod_name == "Config":
                stub.cfgget = lambda k: "test_device"
            elif mod_name == "microIO":
                stub.bind_pin = lambda name, default: default
                stub.pinmap_search = lambda pins: {p: 0 for p in pins}
            elif mod_name == "Types":
                stub.resolve = lambda t, **kw: t
            sys.modules[mod_name] = stub


def _load_module(name, filename):
    _install_stubs()
    spec = importlib.util.spec_from_file_location(name, str(PACKAGE_DIR / filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sim = _load_module("LM_sim800", "LM_sim800.py")
http_mod = _load_module("LM_sim800_http", "LM_sim800_http.py")


def _new_http_inst():
    inst = http_mod.Sim800Http.__new__(http_mod.Sim800Http)
    inst.apn = 'internet'
    inst.user = ''
    inst.pwd = ''
    inst._modem = mock.MagicMock()
    inst._modem.send_command = mock.MagicMock(return_value=b'\r\nOK\r\n')
    inst._modem.uart = mock.MagicMock()
    inst._modem._wait_for_prompt = mock.MagicMock(return_value=b'\r\n> ')
    return inst


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

class TestParseUrl(unittest.TestCase):

    def test_simple_url(self):
        h, p, path = http_mod.Sim800Http._parse_url('http://example.com/api/data')
        self.assertEqual(h, 'example.com')
        self.assertEqual(p, '80')
        self.assertEqual(path, '/api/data')

    def test_url_with_port(self):
        h, p, path = http_mod.Sim800Http._parse_url('http://192.168.1.1:8080/test')
        self.assertEqual(h, '192.168.1.1')
        self.assertEqual(p, '8080')
        self.assertEqual(path, '/test')

    def test_url_no_path(self):
        h, p, path = http_mod.Sim800Http._parse_url('http://example.com')
        self.assertEqual(h, 'example.com')
        self.assertEqual(path, '/')

    def test_url_without_scheme(self):
        h, p, path = http_mod.Sim800Http._parse_url('example.com/api')
        self.assertEqual(h, 'example.com')
        self.assertEqual(path, '/api')


# ---------------------------------------------------------------------------
# HTTP response parsing
# ---------------------------------------------------------------------------

class TestParseHttpResponse(unittest.TestCase):

    def test_parse_200_response(self):
        raw = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"key":"value"}\r\nCLOSED'
        result = http_mod.Sim800Http._parse_http_response(raw)
        self.assertEqual(result['status'], 200)
        self.assertEqual(result['body'], '{"key":"value"}')
        self.assertEqual(result['headers']['content-type'], 'application/json')

    def test_parse_404_response(self):
        raw = b'HTTP/1.1 404 Not Found\r\n\r\nNot Found\r\nCLOSED'
        result = http_mod.Sim800Http._parse_http_response(raw)
        self.assertEqual(result['status'], 404)
        self.assertEqual(result['body'], 'Not Found')

    def test_parse_no_http(self):
        raw = b'garbage data'
        result = http_mod.Sim800Http._parse_http_response(raw)
        self.assertEqual(result['status'], -1)

    def test_parse_empty_body(self):
        raw = b'HTTP/1.1 204 No Content\r\n\r\n\r\nCLOSED'
        result = http_mod.Sim800Http._parse_http_response(raw)
        self.assertEqual(result['status'], 204)

    def test_parse_strips_ok_marker(self):
        raw = b'HTTP/1.1 200 OK\r\n\r\ndata\r\nCLOSED'
        result = http_mod.Sim800Http._parse_http_response(raw)
        self.assertEqual(result['body'], 'data')


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------

class TestBuildRequest(unittest.TestCase):

    def setUp(self):
        self.inst = _new_http_inst()

    def test_get_request(self):
        req = self.inst._build_request('GET', 'example.com', '/api')
        self.assertIn('GET /api HTTP/1.1', req)
        self.assertIn('Host: example.com', req)
        self.assertIn('Connection: close', req)

    def test_post_with_dict_body(self):
        req = self.inst._build_request('POST', 'example.com', '/api', body={'key': 'val'})
        self.assertIn('POST /api HTTP/1.1', req)
        self.assertIn('Content-Type: application/json', req)
        self.assertIn('"key"', req)
        self.assertIn('Content-Length:', req)

    def test_post_with_string_body(self):
        req = self.inst._build_request('POST', 'example.com', '/api', body='raw data')
        self.assertIn('Content-Length: 8', req)
        self.assertIn('raw data', req)

    def test_custom_headers(self):
        req = self.inst._build_request('GET', 'example.com', '/', headers={'Authorization': 'Bearer xyz'})
        self.assertIn('Authorization: Bearer xyz', req)

    def test_custom_content_type_not_overridden(self):
        req = self.inst._build_request('POST', 'example.com', '/',
                                       headers={'content-type': 'text/plain'}, body='data')
        self.assertNotIn('application/json', req)
        self.assertIn('text/plain', req)


# ---------------------------------------------------------------------------
# GPRS connect/disconnect
# ---------------------------------------------------------------------------

class TestGprsConnect(unittest.TestCase):

    def setUp(self):
        self.inst = _new_http_inst()

    def test_connect_success(self):
        self.inst._modem.send_command = mock.MagicMock(
            side_effect=[
                b'\r\nSHUT OK\r\n',   # CIPSHUT
                b'\r\nOK\r\n',         # CIPMUX
                b'\r\nOK\r\n',         # CSTT
                b'\r\nOK\r\n',         # CIICR
                b'\r\n10.20.30.40\r\n', # CIFSR
            ]
        )
        result = self.inst.connect()
        self.assertTrue(result['connected'])
        self.assertEqual(result['ip'], '10.20.30.40')

    def test_connect_failure(self):
        self.inst._modem.send_command = mock.MagicMock(
            side_effect=[
                b'\r\nSHUT OK\r\n',
                b'\r\nOK\r\n',
                b'\r\nOK\r\n',
                b'\r\nOK\r\n',
                b'\r\nERROR\r\n',
            ]
        )
        result = self.inst.connect()
        self.assertFalse(result['connected'])

    def test_disconnect(self):
        self.inst.disconnect()
        self.inst._modem.send_command.assert_called_with('AT+CIPSHUT', 5000)

    def test_is_gprs_connected_true(self):
        self.inst._modem.send_command = mock.MagicMock(
            return_value=b'\r\nOK\r\nSTATE: IP GPRSACT\r\n'
        )
        self.assertTrue(self.inst.is_gprs_connected())

    def test_is_gprs_connected_false(self):
        self.inst._modem.send_command = mock.MagicMock(
            return_value=b'\r\nOK\r\nSTATE: IP INITIAL\r\n'
        )
        self.assertFalse(self.inst.is_gprs_connected())


# ---------------------------------------------------------------------------
# HTTP methods
# ---------------------------------------------------------------------------

class TestHttpMethods(unittest.TestCase):

    def setUp(self):
        self.inst = _new_http_inst()
        self.inst._tcp_connect = mock.MagicMock(return_value=True)
        self.inst._tcp_send = mock.MagicMock(return_value=b'\r\nSEND OK\r\n')
        self.inst._tcp_recv = mock.MagicMock(
            return_value=b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"ok":true}\r\nCLOSED'
        )
        self.inst._tcp_close = mock.MagicMock()

    def test_get(self):
        result = self.inst.get('http://example.com/api')
        self.assertEqual(result['status'], 200)
        self.assertEqual(result['body'], '{"ok":true}')
        self.inst._tcp_connect.assert_called_once_with('example.com', '80', timeout=15000)

    def test_post_with_body(self):
        result = self.inst.post('http://example.com/api', body={'key': 'val'})
        self.assertEqual(result['status'], 200)
        send_data = self.inst._tcp_send.call_args[0][0]
        self.assertIn('POST /api', send_data)
        self.assertIn('"key"', send_data)

    def test_put(self):
        result = self.inst.put('http://example.com/api/1', body='data')
        self.assertEqual(result['status'], 200)
        send_data = self.inst._tcp_send.call_args[0][0]
        self.assertIn('PUT /api/1', send_data)

    def test_delete(self):
        result = self.inst.delete('http://example.com/api/1')
        self.assertEqual(result['status'], 200)
        send_data = self.inst._tcp_send.call_args[0][0]
        self.assertIn('DELETE /api/1', send_data)

    def test_custom_headers(self):
        self.inst.get('http://example.com/api', headers={'X-Token': 'abc'})
        send_data = self.inst._tcp_send.call_args[0][0]
        self.assertIn('X-Token: abc', send_data)

    def test_tcp_connect_failure(self):
        self.inst._tcp_connect = mock.MagicMock(return_value=False)
        result = self.inst.get('http://example.com/api')
        self.assertEqual(result['status'], -1)
        self.assertIn('TCP connect failed', result['body'])

    def test_closes_connection_after_request(self):
        self.inst.get('http://example.com/api')
        self.inst._tcp_close.assert_called_once()

    def test_request_with_port(self):
        self.inst.get('http://192.168.1.100:8080/status')
        self.inst._tcp_connect.assert_called_once_with('192.168.1.100', '8080', timeout=15000)

    def test_retry_on_tcp_connect_failure(self):
        self.inst._tcp_connect = mock.MagicMock(side_effect=[False, False, True])
        result = self.inst.request('GET', 'http://example.com/api', retries=2)
        self.assertEqual(result['status'], 200)
        self.assertEqual(self.inst._tcp_connect.call_count, 3)

    def test_retry_exhausted(self):
        self.inst._tcp_connect = mock.MagicMock(return_value=False)
        result = self.inst.request('GET', 'http://example.com/api', retries=1)
        self.assertEqual(result['status'], -1)
        self.assertEqual(self.inst._tcp_connect.call_count, 2)

    def test_retry_on_empty_response(self):
        self.inst._tcp_recv = mock.MagicMock(
            side_effect=[b'', b'HTTP/1.1 200 OK\r\n\r\nok\r\nCLOSED']
        )
        result = self.inst.request('GET', 'http://example.com/api', retries=1)
        self.assertEqual(result['status'], 200)

    def test_no_retry_on_success(self):
        result = self.inst.request('GET', 'http://example.com/api', retries=2)
        self.assertEqual(result['status'], 200)
        self.inst._tcp_connect.assert_called_once()


# ---------------------------------------------------------------------------
# Module-level functions
# ---------------------------------------------------------------------------

class TestModuleFunctions(unittest.TestCase):

    def setUp(self):
        self.inst = _new_http_inst()
        http_mod.Sim800Http.INSTANCE = self.inst

    def tearDown(self):
        http_mod.Sim800Http.INSTANCE = None

    def test_load_without_sim800(self):
        orig = sim.Sim800.INSTANCE
        sim.Sim800.INSTANCE = None
        http_mod.Sim800Http.INSTANCE = None
        result = http_mod.load()
        self.assertIn('not loaded', result)
        sim.Sim800.INSTANCE = orig

    def test_load_success(self):
        sim.Sim800.INSTANCE = mock.MagicMock()
        http_mod.Sim800Http.INSTANCE = None
        result = http_mod.load(apn='internet.telekom')
        self.assertIn('started', result)
        http_mod.Sim800Http.INSTANCE = None
        sim.Sim800.INSTANCE = None

    def test_load_already_running(self):
        sim.Sim800.INSTANCE = mock.MagicMock()
        result = http_mod.load()
        self.assertIn('already running', result)
        sim.Sim800.INSTANCE = None

    def test_connect_delegates(self):
        self.inst.connect = mock.MagicMock(return_value={'connected': True, 'ip': '1.2.3.4'})
        result = http_mod.connect()
        self.assertTrue(result['connected'])

    def test_get_delegates(self):
        self.inst.get = mock.MagicMock(return_value={'status': 200, 'body': 'ok'})
        result = http_mod.get('http://example.com')
        self.assertEqual(result['status'], 200)

    def test_post_delegates(self):
        self.inst.post = mock.MagicMock(return_value={'status': 201, 'body': ''})
        result = http_mod.post('http://example.com', body='data')
        self.assertEqual(result['status'], 201)


if __name__ == "__main__":
    unittest.main(verbosity=2)
