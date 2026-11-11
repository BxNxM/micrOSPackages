"""Optional BLE shell: public Load Module entrypoint, loaded lazily."""

_BACKEND = None


def _loaded():
    global _BACKEND
    if _BACKEND is None:
        from sys import modules
        _BACKEND = modules.get('Bluetooth')
    return _BACKEND


def _backend():
    global _BACKEND
    if _loaded() is None:
        from sys import path
        from Files import OSPath, path_join
        # The registry folder name collides with the built-in bluetooth module.
        # Import the uppercase core from its installed package directory.
        location = path_join(OSPath.LIB, 'bluetooth')
        if location not in path:
            path.append(location)
        import Bluetooth
        _BACKEND = Bluetooth
    return _BACKEND


def load():
    """Start NUS advertising with exclusive ownership of the BLE controller."""
    return _backend().load()


def stop():
    """Disconnect and stop advertising; worker exits cooperatively."""
    return status() if _loaded() is None else _BACKEND.stop()


def status():
    """Listener and task state; does not activate Bluetooth."""
    if _loaded() is None:
        return {'active': False, 'connected': False,
                'state': 'stopped', 'advertising': False}
    return _BACKEND.status()


def help(widgets=False):
    from Types import resolve
    return resolve(('load', 'status', 'stop'), widgets=widgets)
