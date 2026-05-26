import time
import LM_sim800 as sim800
from Common import console
from Types import resolve


class Sim800Http:
    INSTANCE = None

    def __init__(self, apn, user='', pwd=''):
        self.apn = apn
        self.user = user
        self.pwd = pwd
        self._modem = sim800.Sim800.INSTANCE

    def _cmd(self, command, timeout=1000):
        return self._modem.send_command(command, timeout)

    def _wait_for(self, marker, timeout=10000):
        start_time = time.ticks_ms()
        response = bytearray()
        uart = self._modem.uart
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout:
            if uart.any():
                chunk = uart.read(uart.any())
                if chunk:
                    response.extend(chunk)
                    if marker in response or b'ERROR' in response:
                        break
            time.sleep(0.1)
        return bytes(response)

    def connect(self):
        """
        Activate GPRS and get IP address.
        :return dict: connected (bool), ip (str)
        """
        self._cmd('AT+CIPSHUT', timeout=5000)
        self._cmd('AT+CIPMUX=0')
        self._cmd(f'AT+CSTT="{self.apn}","{self.user}","{self.pwd}"')
        self._cmd('AT+CIICR', timeout=10000)
        resp = self._cmd('AT+CIFSR', timeout=5000)
        try:
            ip = resp.decode().strip()
            lines = [l for l in ip.split('\r\n') if l and 'ERROR' not in l]
            ip = lines[-1] if lines else ''
        except Exception:
            ip = ''
        ok = ip != '' and '.' in ip
        if ok:
            console(f"GPRS connected: {ip}")
        return {'connected': ok, 'ip': ip}

    def disconnect(self):
        """
        Deactivate GPRS connection.
        :return bytes: raw response
        """
        return self._cmd('AT+CIPSHUT', timeout=5000)

    def is_gprs_connected(self):
        """
        Check GPRS connection status.
        :return bool: True if connected
        """
        resp = self._cmd('AT+CIPSTATUS')
        try:
            text = resp.decode()
            return 'CONNECT OK' in text or 'IP STATUS' in text or 'IP GPRSACT' in text
        except Exception:
            return False

    def _tcp_connect(self, host, port, timeout=10000):
        resp = self._cmd(f'AT+CIPSTART="TCP","{host}","{port}"', timeout=2000)
        result = self._wait_for(b'CONNECT OK', timeout=timeout)
        return b'CONNECT OK' in result or b'CONNECT OK' in resp

    def _tcp_send(self, data, timeout=10000):
        data_bytes = data.encode() if isinstance(data, str) else data
        self._cmd(f'AT+CIPSEND={len(data_bytes)}', timeout=2000)
        self._modem._wait_for_prompt(prompt=b'>', timeout=3000)
        self._modem.uart.write(data_bytes)
        return self._wait_for(b'SEND OK', timeout=timeout)

    def _tcp_recv(self, timeout=10000):
        return self._wait_for(b'CLOSED', timeout=timeout)

    def _tcp_close(self):
        return self._cmd('AT+CIPCLOSE', timeout=3000)

    @staticmethod
    def _parse_http_response(raw):
        try:
            text = ''.join(chr(b) for b in raw)
            if 'HTTP/' not in text:
                return {'status': -1, 'body': text}
            header_end = text.find('\r\n\r\n')
            if header_end < 0:
                header_end = text.find('\n\n')
            if header_end < 0:
                return {'status': -1, 'body': text}
            header_part = text[:header_end]
            body = text[header_end:].strip()
            # Remove trailing CLOSED / OK markers
            for marker in ('CLOSED', '\r\nOK\r\n'):
                if body.endswith(marker):
                    body = body[:-len(marker)].strip()
            status_line = header_part.split('\r\n')[0]
            parts = status_line.split(' ', 2)
            status_code = int(parts[1]) if len(parts) > 1 else -1
            headers = {}
            for line in header_part.split('\r\n')[1:]:
                if ':' in line:
                    k, v = line.split(':', 1)
                    headers[k.strip().lower()] = v.strip()
            return {'status': status_code, 'headers': headers, 'body': body}
        except Exception as e:
            console(f"HTTP parse error: {e}")
            return {'status': -1, 'body': ''.join(chr(b) for b in raw)}

    def _build_request(self, method, host, path, headers=None, body=None):
        req = f'{method} {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n'
        if headers:
            for k, v in headers.items():
                req += f'{k}: {v}\r\n'
        if body is not None:
            if isinstance(body, dict):
                import json
                body = json.dumps(body)
            if 'content-type' not in (headers or {}):
                req += 'Content-Type: application/json\r\n'
            req += f'Content-Length: {len(body)}\r\n'
            req += f'\r\n{body}'
        else:
            req += '\r\n'
        return req

    @staticmethod
    def _parse_url(url):
        url = url.replace('http://', '')
        port = '80'
        if '/' in url:
            host_port, path = url.split('/', 1)
            path = '/' + path
        else:
            host_port = url
            path = '/'
        if ':' in host_port:
            host, port = host_port.split(':', 1)
        else:
            host = host_port
        return host, port, path


    def request(self, method, url, headers=None, body=None, timeout=15000, retries=2):
        """
        Send an HTTP request over TCP socket with retry.
        :param method str: HTTP method (GET, POST, PUT, DELETE, PATCH)
        :param url str: full URL (http://host:port/path)
        :param headers dict|None: extra HTTP headers
        :param body str|dict|None: request body (dict auto-serialized to JSON)
        :param timeout int: response timeout in ms
        :param retries int: number of retries on failure (default: 2)
        :return dict: status (int), headers (dict), body (str)
        """
        host, port, path = self._parse_url(url)
        req = self._build_request(method, host, path, headers, body)
        last_err = 'TCP connect failed'
        for attempt in range(1 + retries):
            if attempt > 0:
                console(f"HTTP retry {attempt}/{retries}")
                self._tcp_close()
                time.sleep(1)
            if not self._tcp_connect(host, port, timeout=timeout):
                last_err = 'TCP connect failed'
                continue
            self._tcp_send(req, timeout=timeout)
            raw = self._tcp_recv(timeout=timeout)
            self._tcp_close()
            result = self._parse_http_response(raw)
            if result['status'] > 0:
                return result
            last_err = result.get('body', 'Empty response')
        return {'status': -1, 'body': last_err}

    def get(self, url, headers=None, timeout=15000):
        """
        HTTP GET request.
        :param url str: full URL
        :param headers dict|None: extra headers
        :param timeout int: response timeout in ms
        :return dict: status, headers, body
        """
        return self.request('GET', url, headers=headers, timeout=timeout)

    def post(self, url, body=None, headers=None, timeout=15000):
        """
        HTTP POST request.
        :param url str: full URL
        :param body str|dict|None: request body
        :param headers dict|None: extra headers
        :param timeout int: response timeout in ms
        :return dict: status, headers, body
        """
        return self.request('POST', url, headers=headers, body=body, timeout=timeout)

    def put(self, url, body=None, headers=None, timeout=15000):
        """
        HTTP PUT request.
        :param url str: full URL
        :param body str|dict|None: request body
        :param headers dict|None: extra headers
        :param timeout int: response timeout in ms
        :return dict: status, headers, body
        """
        return self.request('PUT', url, headers=headers, body=body, timeout=timeout)

    def delete(self, url, headers=None, timeout=15000):
        """
        HTTP DELETE request.
        :param url str: full URL
        :param headers dict|None: extra headers
        :param timeout int: response timeout in ms
        :return dict: status, headers, body
        """
        return self.request('DELETE', url, headers=headers, timeout=timeout)


def load(apn='internet.telekom', user='', pwd=''):
    """
    Initialize the HTTP addon.
    :param apn str: GPRS APN (default: 'internet.telekom')
    :param user str: APN username
    :param pwd str: APN password
    :return str: status message
    """
    if sim800.Sim800.INSTANCE is None:
        return 'sim800 not loaded. Call sim800 load first.'
    if Sim800Http.INSTANCE is None:
        Sim800Http.INSTANCE = Sim800Http(apn, user, pwd)
        return 'Sim800Http started.'
    return 'Sim800Http already running.'

def _inst():
    if Sim800Http.INSTANCE is None:
        raise Exception('Not loaded. Call sim800_http load first.')
    return Sim800Http.INSTANCE

def connect():
    """
    Activate GPRS connection.
    :return dict: connected, ip
    """
    return _inst().connect()

def disconnect():
    """
    Deactivate GPRS connection.
    :return bytes: raw response
    """
    return _inst().disconnect()

def is_gprs_connected():
    """
    Check GPRS connection status.
    :return bool: True if connected
    """
    return _inst().is_gprs_connected()

def get(url, headers=None, timeout=15000):
    """
    HTTP GET request.
    :return dict: status, headers, body
    """
    return _inst().get(url, headers=headers, timeout=timeout)

def post(url, body=None, headers=None, timeout=15000):
    """
    HTTP POST request.
    :return dict: status, headers, body
    """
    return _inst().post(url, body=body, headers=headers, timeout=timeout)

def put(url, body=None, headers=None, timeout=15000):
    """
    HTTP PUT request.
    :return dict: status, headers, body
    """
    return _inst().put(url, body=body, headers=headers, timeout=timeout)

def delete(url, headers=None, timeout=15000):
    """
    HTTP DELETE request.
    :return dict: status, headers, body
    """
    return _inst().delete(url, headers=headers, timeout=timeout)

def request(method, url, headers=None, body=None, timeout=15000):
    """
    Generic HTTP request.
    :return dict: status, headers, body
    """
    return _inst().request(method, url, headers=headers, body=body, timeout=timeout)


#######################
# LM helper functions #
#######################

def help(widgets=False):
    """
    [i] micrOS LM naming convention - built-in help message
    :return tuple:
        (widgets=False) list of functions implemented by this application
        (widgets=True) list of widget json for UI generation
    """
    return resolve(('load apn="internet.telekom"',
                    'connect',
                    'disconnect',
                    'is_gprs_connected',
                    'get url="http://example.com/api"',
                    'post url="http://example.com/api" body="{\\"key\\":\\"val\\"}"',
                    'put url="http://example.com/api" body="{\\"key\\":\\"val\\"}"',
                    'delete url="http://example.com/api"',
                    'request method="GET" url="http://example.com/api"'), widgets=widgets)
