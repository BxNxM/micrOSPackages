"""Model MicroPython's force-builtin import with a shadowing namespace cached."""
import builtins
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


def core():
    source = Path(__file__).resolve().parents[1] / 'package/Bluetooth.py'
    spec = importlib.util.spec_from_file_location('ble_import_test_common', source)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_force_builtin_bypasses_filesystem_namespace_and_caches(monkeypatch):
    helper = core()
    namespace = ModuleType('bluetooth')
    namespace.__path__ = ['/lib/bluetooth']
    native = ModuleType('bluetooth')
    native.BLE, native.UUID = object(), object()
    monkeypatch.setitem(sys.modules, 'bluetooth', namespace)
    original_import = builtins.__import__
    original_path = sys.path
    calls = []

    def micropython_import(name, *args, **kwargs):
        if name == 'bluetooth':
            calls.append(sys.path)
            # MicroPython skips its filesystem AND module cache with empty path.
            return native if not sys.path else namespace
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', micropython_import)
    assert helper.firmware() is native
    assert helper.firmware() is native
    assert calls == [()]
    assert sys.path is original_path
    assert sys.modules['bluetooth'] is namespace


@pytest.mark.parametrize('failure', ['missing', 'incomplete'])
def test_path_restored_and_no_cache_on_failure(monkeypatch, failure):
    helper = core()
    original_import = builtins.__import__
    original_path = sys.path
    def micropython_import(name, *args, **kwargs):
        if name == 'bluetooth':
            assert sys.path == ()
            if failure == 'missing':
                raise ImportError('no native bluetooth')
            return ModuleType('bluetooth')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', micropython_import)
    with pytest.raises(RuntimeError, match='BLE-enabled image'):
        helper.firmware()
    assert sys.path is original_path
    assert helper._FIRMWARE is None
