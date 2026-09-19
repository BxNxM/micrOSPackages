/* Direct text WebSocket transport, using the official WebREPL terminal widget. */
(function () {
  'use strict';
  const el = id => document.getElementById(id);
  const backend = el('backend'), message = el('message');
  const connectButton = el('connect'), enableButton = el('enable');
  const container = el('terminal');
  let socket = null, state = null, busy = false, timer = null, canConnect = false;
  let port = 8266;
  const secure = location.protocol === 'https:';
  const term = new Terminal({cols: 80, rows: 24, useStyle: true,
    screenKeys: true, cursorBlink: false, scrollback: 500});
  term.open(container);

  function address() {
    return 'ws://' + location.hostname + ':' + port + '/';
  }

  function controls() {
    const open = socket && socket.readyState === WebSocket.OPEN;
    el('address').textContent = address();
    enableButton.disabled = busy || !state || !state.available || state.active;
    connectButton.disabled = !socket && (secure || !canConnect);
    connectButton.textContent = socket ? 'Disconnect' : 'Connect';
    el('interrupt').disabled = !open;
    el('restart').disabled = !open;
    el('refresh').disabled = busy;
  }

  function showState(data) {
    state = data;
    canConnect = data.available && data.active;
    port = data.port || 8266;
    backend.dataset.state = data.active ? 'active' : 'inactive';
    backend.textContent = !data.available ? 'Backend: unavailable in this firmware' :
      data.active ? 'Backend: active' : 'Backend: inactive';
    controls();
  }

  async function request(path, method) {
    const controller = new AbortController();
    // auth.js may wait for the user to enter a password during POST retries.
    const timeout = method === 'POST' ? null : setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch('/uwebrepl/' + path, {
        method: method || 'GET', cache: 'no-store', signal: controller.signal,
        headers: {Accept: 'application/json'}
      });
      if (!response.ok) throw new Error('Device request failed (' + response.status + ')');
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      if (typeof data.active !== 'boolean' || typeof data.available !== 'boolean') {
        throw new Error('Invalid backend status');
      }
      return data;
    } finally {
      if (timeout !== null) clearTimeout(timeout);
    }
  }

  async function refresh() {
    if (busy) return;
    busy = true;
    controls();
    try {
      showState(await request('status'));
      message.textContent = secure ? 'Open this page over HTTP to connect to WebREPL.' :
        state.active ? 'Ready to connect. Enter the WebREPL password in the terminal.' :
        state.available ? 'Enable WebREPL, then connect. Activation uses your device password.' :
        'This firmware does not provide the supported MicroPython WebREPL backend.';
    } catch (_) {
      state = null;
      backend.dataset.state = 'unknown';
      backend.textContent = 'Backend: status unavailable';
      message.textContent = 'Cannot reach the status API. Run “uwebrepl load” on the device. ' +
        'After Ctrl+C, HTTP may be stopped; an open terminal can still work.';
    } finally {
      busy = false;
      controls();
    }
  }

  enableButton.addEventListener('click', async function () {
    busy = true;
    controls();
    message.textContent = 'Enabling WebREPL…';
    try {
      showState(await request('enable', 'POST'));
      message.textContent = state.active ? 'WebREPL enabled. Connect to open the console.' :
        'WebREPL did not start. Refresh status and check the device.';
    } catch (error) {
      message.textContent = 'Could not enable WebREPL: ' + error.message;
    } finally {
      busy = false;
      controls();
    }
  });

  function send(data) {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(data);
  }
  term.on('data', data => send(data.replace(/\r?\n/g, '\r')));

  connectButton.addEventListener('click', function () {
    if (socket) { socket.close(); return; }
    try {
      const current = new WebSocket(address());
      socket = current;
      el('connection').textContent = 'Console: connecting…';
      controls();
      timer = setTimeout(() => {
        if (socket === current && current.readyState === WebSocket.CONNECTING) {
          message.textContent = 'Connection timed out. Check WebREPL and port ' + port + '.';
          current.close();
        }
      }, 8000);
      current.onopen = function () {
        clearTimeout(timer);
        el('connection').textContent = 'Console: connected (authenticate in terminal)';
        term.write('\r\n[WebREPL connected]\r\n');
        term.focus();
        term.element.focus();
        controls();
      };
      current.onmessage = function (event) {
        if (typeof event.data === 'string') term.write(event.data);
      };
      current.onerror = function () {
        message.textContent = 'WebREPL connection failed. Check the device and close other WebREPL clients.';
      };
      current.onclose = function () {
        clearTimeout(timer);
        if (socket !== current) return;
        socket = null;
        el('connection').textContent = 'Console: disconnected';
        term.write('\r\n[Disconnected]\r\n');
        controls();
      };
    } catch (error) {
      socket = null;
      message.textContent = 'Could not connect: ' + error.message;
      controls();
    }
  });

  el('interrupt').addEventListener('click', function () {
    send('\x03');
    message.textContent = 'Interrupt sent. micrOS and HTTP may stop; keep this console open. Ctrl+D restarts.';
    term.focus();
    term.element.focus();
  });
  el('restart').addEventListener('click', function () {
    send('\x04');
    message.textContent = 'Ctrl+D sent. At the Python prompt this restarts the device. Refresh status after boot.';
  });
  el('refresh').addEventListener('click', refresh);
  function resize() {
    term.resize(Math.max(40, Math.min(150, Math.floor((container.clientWidth - 24) / 8))), 24);
  }
  window.addEventListener('resize', resize);
  window.addEventListener('pagehide', function () { if (socket) socket.close(); });
  resize();
  refresh();
})();
