#!/usr/bin/env python3
"""macOS/CPython NUS shell tester. Install separately: python3 -m pip install bleak."""
import argparse
import asyncio
import codecs
import getpass
import os
import re
import sys

SERVICE = '6e400001-b5a3-f393-e0a9-e50e24dcca9e'
RX = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'
TX = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'


class Terminal:
    def __init__(self, client, disconnected, timeout):
        self.client = client
        self.disconnected = disconnected
        self.timeout = timeout
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.received = ''
        self.changed = asyncio.Event()
        self.prompt_identity = None

    def notify(self, _characteristic, data):
        text = self.decoder.decode(data)
        print(text, end='', flush=True)
        self.received += text
        if len(self.received) > 65536:
            self.received = self.received[-65536:]
        self.changed.set()

    def has_prompt(self):
        """Match the node's complete prompt line, including Shell mode prefixes."""
        line = self.received.rsplit('\n', 1)[-1]
        if not line.endswith(' $ '):
            return False
        identity = line[:-3]
        for prefix in ('[password] ', '[configure] '):
            if identity.startswith(prefix):
                identity = identity[len(prefix):]
        if not identity:
            return False
        if self.prompt_identity is None:
            # The initial empty command returns just the current Shell prompt.
            self.prompt_identity = identity
        return identity == self.prompt_identity

    async def command(self, text):
        encoded = text.encode('utf-8')
        if len(encoded) > 512 or '\n' in text or '\r' in text:
            raise ValueError('Send one command of at most 512 UTF-8 bytes')
        self.received = ''
        self.changed.clear()
        encoded += b'\n'
        async def exchange():
            for offset in range(0, len(encoded), 20):
                await self.client.write_gatt_char(RX, encoded[offset:offset + 20], response=True)
            if text.strip() == 'exit':
                await self.disconnected.wait()
                return self.received
            while not self.has_prompt():
                if self.disconnected.is_set():
                    raise ConnectionError('Board disconnected before the next prompt')
                await self.changed.wait()
                self.changed.clear()
            return self.received
        return await asyncio.wait_for(exchange(), self.timeout)


async def run(args):
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError as error:
        raise RuntimeError('Install tester dependency: python3 -m pip install bleak') from error
    devices = await BleakScanner.discover(timeout=args.scan_timeout,
                                          service_uuids=[SERVICE], return_adv=True)
    matches = []
    for device, advertisement in devices.values():
        name = advertisement.local_name or device.name or ''
        if args.scan:
            print(f'{device.address}  {name}')
        if (args.address and device.address.lower() == args.address.lower()) or (
                args.name and name == args.name):
            matches.append(device)
    if args.scan:
        return
    if len(matches) != 1:
        raise RuntimeError(f'Expected one matching board, found {len(matches)}; use --scan')
    disconnected = asyncio.Event()
    terminal = None
    def on_disconnect(_client):
        disconnected.set()
        if terminal is not None:
            terminal.changed.set()
    async with BleakClient(matches[0], disconnected_callback=on_disconnect) as client:
        terminal = Terminal(client, disconnected, args.timeout)
        await client.start_notify(TX, terminal.notify)
        if not args.test and not args.command:
            print(f'Enter micrOS commands; exit closes the session. Ctrl-C quits. ({matches[0].address})',
                  flush=True)
        prompt = await terminal.command('')
        if '[password]' in prompt:
            password = await asyncio.to_thread(getpass.getpass, '\nmicrOS password: ')
            prompt = await terminal.command(password)
            if 'AuthOk' not in prompt:
                raise RuntimeError('Shell authentication failed')
        if args.test:
            reply = await terminal.command('hello')
            if 'hello:' not in reply:
                raise RuntimeError('Missing shell hello response')
            version = await terminal.command('version')
            if not re.search(r'(?m)^\d+\.\d+\.\d+', version):
                raise RuntimeError('Missing shell version response')
            help_text = await terminal.command('help')
            if '[MICROS]' not in help_text:
                raise RuntimeError('Missing shell help response')
            print('\nBLE shell smoke test passed (hello/version/help).')
        for command in args.command:
            await terminal.command(command)
            if disconnected.is_set():
                return
        if args.test or args.command:
            return
        pending = bytearray()
        while client.is_connected:
            command = await read_line(disconnected, pending)
            await terminal.command(command)
            if disconnected.is_set():
                break


async def read_line(disconnected, pending):
    """Read one command, retaining additional pasted lines for the next call."""
    loop = asyncio.get_running_loop()
    fd = sys.stdin.fileno()
    dropped = asyncio.create_task(disconnected.wait())
    try:
        while not disconnected.is_set():
            end = pending.find(b'\n')
            if end >= 0:
                line = bytes(pending[:end])
                del pending[:end + 1]
                return line.decode(sys.stdin.encoding or 'utf-8').rstrip('\r')
            chunk = loop.create_future()

            def ready():
                if not chunk.done():
                    try:
                        chunk.set_result(os.read(fd, 4096))
                    except OSError as error:
                        chunk.set_exception(error)

            loop.add_reader(fd, ready)
            try:
                done, _ = await asyncio.wait((chunk, dropped), return_when=asyncio.FIRST_COMPLETED)
                if dropped in done:
                    break
                data = chunk.result()
            finally:
                loop.remove_reader(fd)
                chunk.cancel()
            if not data:
                if pending:
                    line = bytes(pending)
                    pending.clear()
                    return line.decode(sys.stdin.encoding or 'utf-8').rstrip('\r')
                raise EOFError()
            pending.extend(data)
        raise ConnectionError('Board disconnected')
    finally:
        dropped.cancel()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument('--scan', action='store_true', help='List advertising NUS boards')
    selector.add_argument('--name', help='Exact advertised device name')
    selector.add_argument('--address', help='Device UUID on macOS, address on other platforms')
    parser.add_argument('--test', action='store_true', help='Check hello, version and help')
    parser.add_argument('-c', '--command', action='append', default=[], help='Command; repeatable')
    parser.add_argument('--scan-timeout', type=float, default=8)
    parser.add_argument('--timeout', type=float, default=30, help='Per-command response timeout')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (KeyboardInterrupt, EOFError):
        pass
    except Exception as error:
        parser.exit(1, f'BLE shell: {error}\n')


if __name__ == '__main__':
    main()
