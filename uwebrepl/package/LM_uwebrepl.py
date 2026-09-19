"""On-device WebREPL console. Loading the UI never starts the listener."""

from Auth import sudo
from Common import web_endpoint
from Config import cfgget
from Types import resolve


def _backend():
    # Keep WebREPL's socket/crypto imports out of LM import and page registration.
    import webrepl
    if not hasattr(webrepl, 'listen_s'):
        raise ImportError('Firmware has no supported WebREPL backend')
    return webrepl


def status():
    """Read the real listener, including one started by the micrOS shell."""
    result = {'available': True, 'active': False, 'port': 8266}
    try:
        backend = _backend()
    except ImportError:
        result['available'] = False
        return result
    listener = backend.listen_s
    if listener is not None:
        try:
            # ESP32/lwIP sockets have no getsockname(). Poll without accepting
            # clients or altering the listener's WebREPL callback/timeout.
            from select import poll, POLLIN
            probe = poll()
            probe.register(listener, POLLIN)
            # Idle or readable is healthy; ERR/HUP/NVAL means failed/closed.
            # Upstream stop() leaves a closed socket object in listen_s.
            result['active'] = not any(event[1] & ~POLLIN for event in probe.poll(0))
            if result['active'] and hasattr(listener, 'getsockname'):
                result['port'] = listener.getsockname()[1]
        except (OSError, ValueError):
            result['active'] = False
    return result


def _enable():
    state = status()
    if not state['available']:
        raise RuntimeError('WebREPL is unavailable in this firmware')
    if not state['active']:
        # Same password and background mode as the built-in shell command.
        backend = _backend()
        try:
            backend.start(password=cfgget('appwd'))
        except Exception:
            backend.stop()
            raise
    return status()


@sudo
def enable():
    """Enable WebREPL until reboot; requires pwd=<appwd>. Idempotent."""
    return _enable()


@sudo
def disable():
    """Stop WebREPL and disconnect its client; requires pwd=<appwd>."""
    _backend().stop()
    return status()


def _status_get(*_):
    return 'application/json', status()


@sudo
def _enable_post(*_):
    try:
        return 'application/json', _enable()
    except Exception as error:
        return 'application/json', {'error': str(error)}


def load():
    """Register /uwebrepl and its API without enabling WebREPL."""
    web_endpoint('uwebrepl', 'uwebrepl/index.html')
    web_endpoint('uwebrepl/status', _status_get)
    web_endpoint('uwebrepl/enable', _enable_post, 'POST')
    return 'WebREPL UI: /uwebrepl (listener unchanged)'


def help(widgets=False):
    """Public shell commands and dashboard status metadata."""
    return resolve(('load', 'status', 'enable pwd=<appwd>',
                    'disable pwd=<appwd>'), widgets=widgets)
