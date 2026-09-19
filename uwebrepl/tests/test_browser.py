"""Opt-in Chromium smoke tests; no device or network server is contacted.

UWEBREPL_BROWSER_TESTS=1 python3 -m pytest tests/test_browser.py
Requires Playwright and its Chromium browser.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get('UWEBREPL_BROWSER_TESTS') != '1', reason='opt-in browser tests')
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'package' / 'uwebrepl'
AUTH = ROOT.parents[1] / 'source' / 'web' / 'auth.js'


@pytest.fixture(scope='module')
def browser():
    api = pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def ui(browser):
    context = browser.new_context(viewport={'width': 1100, 'height': 900})
    page = context.new_page()
    data = {'available': True, 'active': False, 'port': 8266}
    calls, received, sockets, errors = [], [], [], []
    offline = [False]
    page.on('pageerror', lambda error: errors.append(str(error)))

    def route(request):
        path = urlsplit(request.request.url).path
        calls.append((path, request.request.method))
        if path in ('/uwebrepl/status', '/uwebrepl/enable'):
            if offline[0]:
                request.abort()
                return
            if path.endswith('/enable'):
                if request.request.headers.get('x-micros-auth') != 'test-pass':
                    request.fulfill(status=401, content_type='application/json', body='{}')
                    return
                data['active'] = True
            request.fulfill(content_type='application/json', body=json.dumps(data))
            return
        file = AUTH if path == '/auth.js' else ASSETS / (
            'index.html' if path == '/uwebrepl' else path.removeprefix('/uwebrepl/'))
        if file.is_file():
            request.fulfill(path=str(file))
        else:
            request.fulfill(status=404)

    def websocket(socket):
        sockets.append(socket)
        socket.on_message(lambda message: received.append(message))
        socket.send('Password: ')

    page.route('**/*', route)
    page.route_web_socket('**/*', websocket)
    yield page, data, calls, received, sockets, offline
    assert not errors
    context.close()


def test_activation_auth_terminal_and_http_loss(ui):
    from playwright.sync_api import expect
    page, data, calls, received, sockets, offline = ui
    page.goto('http://device.test/uwebrepl')
    expect(page.locator('#backend')).to_have_text('Backend: inactive')
    expect(page.locator('#connect')).to_be_disabled()
    assert not any(method == 'POST' for _, method in calls)
    page.locator('#enable').click()
    page.locator('input[name=pass]').fill('wrong')
    page.get_by_text('Unlock', exact=True).click()
    expect(page.locator('#micrOSAuth span')).to_have_text('Access denied')
    assert not data['active']
    page.locator('input[name=pass]').fill('test-pass')
    page.get_by_text('Unlock', exact=True).click()
    expect(page.locator('#backend')).to_have_text('Backend: active')
    page.locator('#connect').click()
    expect(page.locator('#connection')).to_contain_text('connected (authenticate')
    expect(page.locator('#terminal')).to_contain_text('Password:')
    page.keyboard.type('test-pass')
    page.keyboard.press('Enter')
    page.wait_for_function('true')
    assert ''.join(received) == 'test-pass\r'
    sockets[0].send('\r\nWebREPL connected\r\n>>> ')
    expect(page.locator('#terminal')).to_contain_text('>>>')
    page.keyboard.press('ArrowUp')
    page.keyboard.press('Backspace')
    page.locator('#interrupt').click()
    assert received[-1] == '\x03'
    assert '\x1b[A' in received
    offline[0] = True
    page.locator('#refresh').click()
    expect(page.locator('#backend')).to_have_text('Backend: status unavailable')
    expect(page.locator('#connect')).to_be_enabled()
    sockets[0].send('\r\nStill connected\r\n>>> ')
    expect(page.locator('#terminal')).to_contain_text('Still connected')
    page.locator('#restart').click()
    assert received[-1] == '\x04'
    page.screenshot(path='/tmp/uwebrepl-desktop.png', full_page=True)
    page.locator('#connect').click()
    expect(page.locator('#connection')).to_have_text('Console: disconnected')
    # HTTP may remain stopped after Ctrl+C; the loaded client can reconnect.
    expect(page.locator('#connect')).to_be_enabled()
    page.locator('#connect').click()
    expect(page.locator('#connection')).to_contain_text('connected (authenticate')


def test_external_listener_reconnect_and_mobile(ui):
    from playwright.sync_api import expect
    page, data, _, _, sockets, _ = ui
    data.update(active=True, port=9000)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto('http://device.test:8080/uwebrepl')
    expect(page.locator('#address')).to_have_text('ws://device.test:9000/')
    expect(page.locator('#enable')).to_be_disabled()
    page.locator('#connect').click()
    expect(page.locator('#connection')).to_contain_text('connected (authenticate')
    sockets[0].close()
    expect(page.locator('#connection')).to_have_text('Console: disconnected')
    page.locator('#connect').click()
    expect(page.locator('#connection')).to_contain_text('connected (authenticate')
    assert len(sockets) == 2
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='/tmp/uwebrepl-mobile.png', full_page=True)


def test_unavailable_firmware(ui):
    from playwright.sync_api import expect
    page, data, _, _, _, _ = ui
    data['available'] = False
    page.goto('http://device.test/uwebrepl')
    expect(page.locator('#backend')).to_contain_text('unavailable in this firmware')
    expect(page.locator('#enable')).to_be_disabled()
    expect(page.locator('#connect')).to_be_disabled()


def test_https_blocks_plain_websocket(ui):
    from playwright.sync_api import expect
    page, data, _, _, _, _ = ui
    data['active'] = True
    page.goto('https://device.test/uwebrepl')
    expect(page.locator('#message')).to_contain_text('Open this page over HTTP')
    expect(page.locator('#connect')).to_be_disabled()


def test_status_error_recovers(ui):
    from playwright.sync_api import expect
    page, _, _, _, _, offline = ui
    offline[0] = True
    page.goto('http://device.test/uwebrepl')
    expect(page.locator('#backend')).to_have_text('Backend: status unavailable')
    expect(page.locator('#enable')).to_be_disabled()
    offline[0] = False
    page.locator('#refresh').click()
    expect(page.locator('#backend')).to_have_text('Backend: inactive')
    expect(page.locator('#enable')).to_be_enabled()
