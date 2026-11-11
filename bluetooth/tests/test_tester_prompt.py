"""Host terminal response framing and command deadline regressions."""
import asyncio
import importlib.util
from pathlib import Path

import pytest


def load_tester():
    source = Path(__file__).resolve().parents[1] / 'helpers/ble_shell.py'
    spec = importlib.util.spec_from_file_location('ble_shell_prompt_tests', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notification_suffix_does_not_finish_command():
    tester = load_tester()

    async def scenario():
        class Client:
            async def write_gatt_char(self, *_args, **_kwargs):
                pass

        terminal = tester.Terminal(Client(), asyncio.Event(), 1)
        initial = asyncio.create_task(terminal.command(''))
        await asyncio.sleep(0)
        terminal.notify(None, b'[password] TinyDevBoard $ ')
        assert await initial == '[password] TinyDevBoard $ '
        assert terminal.prompt_identity == 'TinyDevBoard'

        command = asyncio.create_task(terminal.command('hello'))
        await asyncio.sleep(0)
        terminal.notify(None, b'value happens to $ ')
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not command.done()
        terminal.notify(None, b'continue\nother-node $ ')
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not command.done()
        terminal.notify(None, b'continue\nTinyDevBoard $ ')
        assert await command == (
            'value happens to $ continue\nother-node $ continue\nTinyDevBoard $ ')

    asyncio.run(scenario())


@pytest.mark.parametrize('prefix', ['', '[password] ', '[configure] ', '[password] [configure] '])
def test_prompt_requires_line_boundary_and_accepts_shell_modes(prefix):
    tester = load_tester()
    terminal = tester.Terminal(None, asyncio.Event(), 1)
    terminal.received = '[password] TinyDevBoard $ '
    assert terminal.has_prompt()
    terminal.received = 'response prefix TinyDevBoard $ '
    assert not terminal.has_prompt()
    terminal.received = 'response\n' + prefix + 'TinyDevBoard $ '
    assert terminal.has_prompt()


def test_command_deadline_covers_blocked_gatt_write():
    tester = load_tester()

    async def scenario():
        cancelled = asyncio.Event()

        class Client:
            async def write_gatt_char(self, *_args, **_kwargs):
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        terminal = tester.Terminal(Client(), asyncio.Event(), 0.001)
        with pytest.raises(asyncio.TimeoutError):
            await terminal.command('hello')
        assert cancelled.is_set()

    asyncio.run(scenario())


def test_pasted_commands_do_not_wait_for_more_input(monkeypatch):
    import os
    import sys

    tester = load_tester()
    read_fd, write_fd = os.pipe()
    with os.fdopen(read_fd, encoding='utf-8') as stdin:
        monkeypatch.setattr(sys, 'stdin', stdin)
        try:
            os.write(write_fd, b'hello\r\nversion\n')

            async def scenario():
                disconnected = asyncio.Event()
                pending = bytearray()
                assert await tester.read_line(disconnected, pending) == 'hello'
                assert await tester.read_line(disconnected, pending) == 'version'

            # The writer stays open: there is no further input or EOF to wake the reader.
            asyncio.run(asyncio.wait_for(scenario(), 1))
        finally:
            os.close(write_fd)
