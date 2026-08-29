import json
import time
import struct
from machine import Pin, UART
from Config import cfgget
from Common import console, micro_task
from Debug import syslog
from Notify import Notify
from microIO import bind_pin, pinmap_search
from Types import resolve

# MQTT Control Packet Types
_CONNECT = 0x10
_CONNACK = 0x20
_PUBLISH = 0x30
_PUBACK = 0x40
_SUBSCRIBE = 0x80
_SUBACK = 0x90
_UNSUBSCRIBE = 0xA0
_UNSUBACK = 0xB0
_PINGREQ = 0xC0
_PINGRESP = 0xD0
_DISCONNECT = 0xE0


class Sim800Mqtt(Notify):
    INSTANCE = None
    _BASE_TOPIC = None

    def __init__(self, pin_code, apn, apn_user='', apn_pwd='',
                 server='', port=1883, client_id=None, user=None, password=None,
                 keepalive=60, clean_session=False,
                 will_topic=None, will_msg=None, will_qos=0,
                 reconnect_interval=5, max_reconnect_interval=60,
                 tx_pin=16, rx_pin=17, baudrate=115200):
        # UART / modem
        self.uart_no = 1
        self.sim_pin_code = str(pin_code)
        self.baudrate = baudrate
        self.tx_pin = Pin(bind_pin("sim800_tx", tx_pin))
        self.rx_pin = Pin(bind_pin("sim800_rx", rx_pin))
        self.uart = None
        # GPRS
        self.apn = apn
        self.apn_user = apn_user
        self.apn_pwd = apn_pwd
        # MQTT
        self.server = server
        self.port = str(port)
        self.client_id = client_id or "sim800mqtt_{:.0f}".format(time.time() % 100000)
        self.user = user
        self.password = password
        self.keepalive = keepalive
        self.clean_session = clean_session
        self.will_topic = will_topic
        self.will_msg = will_msg
        self.will_qos = will_qos
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_interval = max_reconnect_interval
        # State
        self._connected = False
        self._msg_id = 0
        self._pending_acks = {}
        self._subscribers = {}
        self._listener_task = None
        self._recv_buf = bytearray()
        self._cmd_subscribed = False
        self._devfid = cfgget('devfid')
        Sim800Mqtt._BASE_TOPIC = self._devfid

    # ---- AT command layer ----

    def _send_at(self, command, timeout=1000, check_ok=True):
        console('SIM800MQTT AT> {}'.format(command))
        self.uart.write(command + '\r')
        time.sleep(0.1)
        resp = self._read_response(timeout, check_ok)
        console('SIM800MQTT AT< {}'.format(resp))
        return resp

    def _read_response(self, timeout=1000, check_ok=True):
        start = time.ticks_ms()
        buf = bytearray()
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.uart.any():
                chunk = self.uart.read(self.uart.any())
                if chunk:
                    buf.extend(chunk)
                    if check_ok and (b'OK' in buf or b'ERROR' in buf):
                        break
            time.sleep(0.05)
        return bytes(buf)

    def _wait_for(self, marker, timeout=10000):
        start = time.ticks_ms()
        buf = bytearray()
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.uart.any():
                chunk = self.uart.read(self.uart.any())
                if chunk:
                    buf.extend(chunk)
                    if marker and marker in buf:
                        break
                    if b'ERROR' in buf:
                        break
            time.sleep(0.05)
        return bytes(buf)

    def _wait_for_prompt(self, prompt=b'>', timeout=3000):
        start = time.ticks_ms()
        buf = bytearray()
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.uart.any():
                chunk = self.uart.read(self.uart.any())
                if chunk:
                    buf.extend(chunk)
                    if prompt in buf or b'ERROR' in buf:
                        break
            time.sleep(0.05)
        return bytes(buf)

    # ---- Modem init ----

    def init_modem(self, retries=5, retry_delay=2):
        self.uart = UART(self.uart_no, baudrate=self.baudrate,
                         tx=self.tx_pin, rx=self.rx_pin)
        # Clean up any previous TCP/GPRS state
        self._send_at('AT', timeout=500)
        self._send_at('AT+CIPSHUT', timeout=5000)
        self._send_at('AT+CGATT=0', timeout=5000)
        for attempt in range(retries):
            resp = self._send_at('AT')
            if b'OK' in resp:
                break
            console("SIM800MQTT modem not ready, retry {}/{}".format(attempt + 1, retries))
            time.sleep(retry_delay)
        else:
            return False
        self._send_at('ATE0')
        self._send_at('AT+CMEE=2')
        # Unlock SIM
        resp = self._send_at('AT+CPIN?')
        if b'READY' not in resp:
            self._send_at('AT+CPIN="{}"'.format(self.sim_pin_code))
            time.sleep(5)
            resp = self._send_at('AT+CPIN?')
            if b'READY' not in resp:
                console("SIM800MQTT: SIM PIN failed")
                return False
        self._send_at('AT+CFUN=1')
        # Wait for network registration
        for _ in range(20):
            resp = self._send_at('AT+CREG?')
            if b'+CREG: 0,1' in resp or b'+CREG: 0,5' in resp:
                return True
            time.sleep(1)
        console("SIM800MQTT: network registration failed")
        return False

    # ---- GPRS / TCP ----

    def _gprs_connect(self):
        self._send_at('AT+CIPSHUT', timeout=5000)
        self._send_at('AT+CIPMUX=0')
        self._send_at('AT+CSTT="{}","{}","{}"'.format(self.apn, self.apn_user, self.apn_pwd))
        self._send_at('AT+CIICR', timeout=10000)
        resp = self._send_at('AT+CIFSR', timeout=5000, check_ok=False)
        if b'ERROR' in resp:
            return False
        return True

    def _tcp_connect(self):
        if not self._gprs_connect():
            return False
        self._send_at('AT+CIPSTART="TCP","{}","{}"'.format(self.server, self.port), timeout=2000)
        resp = self._wait_for(b'CONNECT OK', timeout=15000)
        return b'CONNECT OK' in resp

    def _tcp_send(self, data, wait_send_ok=True):
        data_bytes = data if isinstance(data, (bytes, bytearray)) else data.encode()
        self._send_at('AT+CIPSEND={}'.format(len(data_bytes)), timeout=2000, check_ok=False)
        self._wait_for_prompt(prompt=b'>', timeout=3000)
        self.uart.write(data_bytes)
        if wait_send_ok:
            resp = self._wait_for(b'SEND OK', timeout=10000)
            return b'SEND OK' in resp
        time.sleep(0.3)
        return True

    def _tcp_close(self):
        return self._send_at('AT+CIPCLOSE', timeout=3000)

    def _tcp_read(self):
        if not self.uart.any():
            return None
        time.sleep(0.05)
        data = self.uart.read(self.uart.any())
        return data

    # ---- MQTT packet building ----

    @staticmethod
    def _encode_remaining_length(length):
        buf = bytearray()
        while True:
            byte = length % 128
            length //= 128
            if length > 0:
                byte |= 0x80
            buf.append(byte)
            if length == 0:
                break
        return buf

    @staticmethod
    def _encode_utf8(s):
        encoded = s.encode() if isinstance(s, str) else s
        return struct.pack('!H', len(encoded)) + encoded

    def _next_msg_id(self):
        self._msg_id = (self._msg_id % 65535) + 1
        return self._msg_id

    def _build_connect(self):
        protocol = b'\x00\x04MQTT\x04'
        flags = 0x02 if self.clean_session else 0x00
        if self.user:
            flags |= 0x80
        if self.password:
            flags |= 0x40
        if self.will_topic:
            flags |= 0x04
            flags |= (self.will_qos & 0x03) << 3
        var_header = protocol + struct.pack('!BH', flags, self.keepalive)
        payload = self._encode_utf8(self.client_id)
        if self.will_topic:
            payload += self._encode_utf8(self.will_topic)
            payload += self._encode_utf8(self.will_msg or '')
        if self.user:
            payload += self._encode_utf8(self.user)
        if self.password:
            payload += self._encode_utf8(self.password)
        remaining = var_header + payload
        return bytes([_CONNECT]) + self._encode_remaining_length(len(remaining)) + remaining

    def _build_publish(self, topic, payload, qos=0, msg_id=None, dup=False):
        header = _PUBLISH | (qos << 1)
        if dup:
            header |= 0x08
        var_header = self._encode_utf8(topic)
        if qos > 0 and msg_id is not None:
            var_header += struct.pack('!H', msg_id)
        body = payload.encode() if isinstance(payload, str) else payload
        remaining = var_header + body
        return bytes([header]) + self._encode_remaining_length(len(remaining)) + remaining

    def _build_subscribe(self, topic, qos=0):
        msg_id = self._next_msg_id()
        var_header = struct.pack('!H', msg_id)
        payload = self._encode_utf8(topic) + bytes([qos])
        remaining = var_header + payload
        return bytes([_SUBSCRIBE | 0x02]) + self._encode_remaining_length(len(remaining)) + remaining, msg_id

    def _build_unsubscribe(self, topic):
        msg_id = self._next_msg_id()
        var_header = struct.pack('!H', msg_id)
        payload = self._encode_utf8(topic)
        remaining = var_header + payload
        return bytes([_UNSUBSCRIBE | 0x02]) + self._encode_remaining_length(len(remaining)) + remaining, msg_id

    @staticmethod
    def _build_pingreq():
        return bytes([_PINGREQ, 0x00])

    @staticmethod
    def _build_disconnect():
        return bytes([_DISCONNECT, 0x00])

    @staticmethod
    def _build_puback(msg_id):
        return bytes([_PUBACK, 0x02]) + struct.pack('!H', msg_id)

    # ---- MQTT packet parsing ----

    @staticmethod
    def _decode_remaining_length(data, offset=1):
        multiplier = 1
        value = 0
        idx = offset
        while idx < len(data):
            byte = data[idx]
            value += (byte & 0x7F) * multiplier
            idx += 1
            if not (byte & 0x80):
                break
            multiplier *= 128
        return value, idx - offset

    def _parse_packet(self, data):
        if len(data) < 2:
            return None
        remaining, len_bytes = self._decode_remaining_length(data, 1)
        total = 1 + len_bytes + remaining
        if len(data) < total:
            return None
        payload = data[1 + len_bytes:total]
        return data[0] & 0xF0, data[0], payload, total

    def _handle_packet(self, ptype, first_byte, payload):
        if ptype == _CONNACK:
            if len(payload) >= 2 and payload[1] == 0:
                self._connected = True
                console("SIM800MQTT connected")
            else:
                rc = payload[1] if len(payload) >= 2 else -1
                console("SIM800MQTT connect failed: rc={}".format(rc))
        elif ptype == _PUBLISH:
            self._handle_publish(first_byte, payload)
        elif ptype == _PUBACK:
            if len(payload) >= 2:
                msg_id = struct.unpack('!H', payload[:2])[0]
                self._pending_acks.pop(msg_id, None)
        elif ptype == _PINGRESP:
            pass

    def _handle_publish(self, first_byte, payload):
        qos = (first_byte >> 1) & 0x03
        topic_len = struct.unpack('!H', payload[:2])[0]
        topic = payload[2:2 + topic_len].decode()
        offset = 2 + topic_len
        msg_id = None
        if qos > 0:
            msg_id = struct.unpack('!H', payload[offset:offset + 2])[0]
            offset += 2
        message = payload[offset:]
        try:
            message = message.decode()
        except Exception:
            pass
        if qos == 1 and msg_id is not None:
            self._tcp_send(self._build_puback(msg_id), wait_send_ok=False)
        console('SIM800MQTT Topic: "{}" Msg: "{}"'.format(topic, message))
        # Command dispatch: devfid/loadmodule/function -> lm_execute
        topic_parts = topic.split('/')
        if len(topic_parts) == 3:
            cmd_payload = {}
            if isinstance(message, str) and message.strip():
                try:
                    cmd_payload = json.loads(message)
                except ValueError:
                    pass
            args = ['{}="{}"'.format(k, v) if isinstance(v, str) else '{}={}'.format(k, v)
                    for k, v in cmd_payload.items()]
            cmd_parts = topic_parts[1:] + args
            state, output_json = self.lm_execute(cmd_parts, jsonify=True, secure=False)
            try:
                output = json.loads(output_json)
            except (ValueError, TypeError):
                output = output_json
            resp = json.dumps({'state': state, 'result': output})
            resp_topic = '{}/response'.format(topic)
            self.publish(resp_topic, resp)
        # User callbacks
        for sub_topic, (callback, _) in self._subscribers.items():
            if self._topic_match(sub_topic, topic):
                try:
                    callback(topic, message)
                except Exception as e:
                    console("SIM800MQTT cb error ({}): {}".format(topic, e))

    @staticmethod
    def _topic_match(pattern, topic):
        if pattern == topic:
            return True
        p_parts = pattern.split('/')
        t_parts = topic.split('/')
        for i, p in enumerate(p_parts):
            if p == '#':
                return True
            if i >= len(t_parts):
                return False
            if p != '+' and p != t_parts[i]:
                return False
        return len(p_parts) == len(t_parts)

    def _process_recv_buf(self):
        while True:
            result = self._parse_packet(self._recv_buf)
            if result is None:
                break
            ptype, first_byte, payload, total = result
            self._handle_packet(ptype, first_byte, payload)
            self._recv_buf = self._recv_buf[total:]

    def _retry_pending(self):
        now = time.time()
        for msg_id, (topic, payload, ts) in list(self._pending_acks.items()):
            if now - ts > 10:
                pkt = self._build_publish(topic, payload, qos=1, msg_id=msg_id, dup=True)
                self._tcp_send(pkt, wait_send_ok=False)
                self._pending_acks[msg_id] = (topic, payload, now)

    # ---- Notify interface ----

    @staticmethod
    def send_msg(text, *args, **kwargs):
        inst = Sim800Mqtt.INSTANCE
        if inst is None or not inst._connected:
            return
        suffix = kwargs.get('topic', 'notify')
        topic = "{}/{}".format(Sim800Mqtt._BASE_TOPIC, suffix)
        try:
            inst.publish(topic, str(text))
        except Exception as e:
            syslog("[ERR] SIM800MQTT: {}".format(e))

    # ---- Public API ----

    def connect(self):
        if not self._tcp_connect():
            console("SIM800MQTT TCP connect failed")
            return False
        pkt = self._build_connect()
        self._tcp_send(pkt, wait_send_ok=True)
        # Wait for CONNACK - read whatever comes after SEND OK
        resp = self._read_response(timeout=10000, check_ok=False)
        console('SIM800MQTT CONNACK raw: {}'.format(resp))
        if resp:
            self._recv_buf.extend(resp)
            self._process_recv_buf()
        if self._connected:
            super().add_subscriber(self)
        return self._connected

    def disconnect(self):
        if self._connected:
            try:
                self._tcp_send(self._build_disconnect(), wait_send_ok=False)
            except Exception:
                pass
        self._connected = False
        self._tcp_close()
        self._listener_task = None
        self._pending_acks.clear()
        return "SIM800MQTT disconnected"

    def publish(self, topic, payload, qos=0):
        if not self._connected:
            return False
        msg_id = None
        if qos == 1:
            msg_id = self._next_msg_id()
        pkt = self._build_publish(topic, payload, qos, msg_id)
        self._tcp_send(pkt, wait_send_ok=False)
        if qos == 1 and msg_id is not None:
            self._pending_acks[msg_id] = (topic, payload, time.time())
        return True

    def subscribe_topic(self, topic, callback, qos=0):
        if not self._connected:
            return False
        self._subscribers[topic] = (callback, qos)
        pkt, _ = self._build_subscribe(topic, qos)
        self._tcp_send(pkt, wait_send_ok=False)
        return True

    def unsubscribe_topic(self, topic):
        if not self._connected:
            return False
        self._subscribers.pop(topic, None)
        pkt, _ = self._build_unsubscribe(topic)
        self._tcp_send(pkt, wait_send_ok=False)
        return True

    def reconnect(self):
        self._connected = False
        self._recv_buf = bytearray()
        try:
            self._tcp_close()
        except Exception:
            pass
        if not self._tcp_connect():
            return False
        pkt = self._build_connect()
        self._tcp_send(pkt, wait_send_ok=True)
        resp = self._read_response(timeout=10000, check_ok=False)
        console('SIM800MQTT reconnect CONNACK raw: {}'.format(resp))
        if resp:
            self._recv_buf.extend(resp)
            self._process_recv_buf()
        if not self._connected:
            return False
        for topic, (callback, qos) in self._subscribers.items():
            pkt, _ = self._build_subscribe(topic, qos)
            self._tcp_send(pkt, wait_send_ok=False)
        return True

    def is_connected(self):
        return self._connected

    # ---- Async listener ----

    async def _run_listener(self):
        with micro_task(tag='sim800mqtt.listener') as task:
            last_ping = time.time()
            retry_wait = self.reconnect_interval
            # Deferred cmd topic subscribe
            if self._connected and not self._cmd_subscribed:
                self._subscribe_cmd_topic()
            while True:
                if not self._connected:
                    console("SIM800MQTT reconnecting in {}s...".format(retry_wait))
                    await task.feed(sleep_ms=retry_wait * 1000)
                    if self.reconnect():
                        last_ping = time.time()
                        retry_wait = self.reconnect_interval
                    else:
                        retry_wait = min(retry_wait * 2, self.max_reconnect_interval)
                    continue
                try:
                    data = self._tcp_read()
                    if data:
                        self._recv_buf.extend(data)
                        self._process_recv_buf()
                    now = time.time()
                    if now - last_ping >= self.keepalive // 2:
                        self._tcp_send(self._build_pingreq(), wait_send_ok=False)
                        last_ping = now
                    if self._pending_acks:
                        self._retry_pending()
                    await task.feed(sleep_ms=500)
                except Exception as e:
                    console("SIM800MQTT listener error: {}".format(e))
                    self._connected = False

    def _subscribe_cmd_topic(self):
        """Subscribe to devfid/# for command dispatch."""
        cmd_topic = '{}/#'.format(self._devfid)
        self._subscribers[cmd_topic] = (None, 1)
        pkt, _ = self._build_subscribe(cmd_topic, 1)
        self._tcp_send(pkt, wait_send_ok=False)
        self._cmd_subscribed = True
        console('SIM800MQTT subscribed: {}'.format(cmd_topic))

    def start_listener(self):
        if self._listener_task is None and self._connected:
            self._listener_task = micro_task(tag='sim800mqtt.listener', task=self._run_listener())
        return self._listener_task is not None


# ---- Module-level API ----

def _inst():
    if Sim800Mqtt.INSTANCE is None:
        raise Exception('Not loaded. Call sim800mqtt load first.')
    return Sim800Mqtt.INSTANCE


def load(pin_code, apn, apn_user='', apn_pwd='',
         server='', port=1883, client_id=None, user=None, password=None,
         keepalive=60, clean_session=False,
         will_topic=None, will_msg=None, will_qos=0,
         tx_pin=16, rx_pin=17):
    """
    Initialize SIM800 modem, GPRS, and connect MQTT.
    :param pin_code: SIM PIN code
    :param apn str: APN for GPRS
    :param apn_user str: APN username
    :param apn_pwd str: APN password
    :param server str: MQTT broker hostname or IP
    :param port int: MQTT broker port
    :param client_id str: MQTT client ID
    :param user str: MQTT username
    :param password str: MQTT password
    :param keepalive int: keepalive interval in seconds
    :param clean_session bool: MQTT clean session flag
    :param will_topic str: Last Will topic
    :param will_msg str: Last Will message
    :param will_qos int: Last Will QoS (0 or 1)
    :param tx_pin int: UART TX GPIO pin (default: 16)
    :param rx_pin int: UART RX GPIO pin (default: 17)
    :return str: status message
    """
    if Sim800Mqtt.INSTANCE is not None:
        return 'SIM800MQTT already running.'
    inst = Sim800Mqtt(pin_code, apn, apn_user, apn_pwd,
                      server, port, client_id, user, password,
                      keepalive, clean_session,
                      will_topic, will_msg, will_qos,
                      tx_pin=tx_pin, rx_pin=rx_pin)
    if not inst.init_modem():
        return 'SIM800MQTT modem init failed.'
    if inst.connect():
        Sim800Mqtt.INSTANCE = inst
        inst.start_listener()
        return 'SIM800MQTT started.'
    return 'SIM800MQTT connect failed.'


def unload():
    """Disconnect and clear instance."""
    if Sim800Mqtt.INSTANCE is not None:
        Sim800Mqtt.INSTANCE.disconnect()
        Sim800Mqtt.INSTANCE = None
        return 'SIM800MQTT stopped.'
    return 'SIM800MQTT not running.'


def publish(topic, payload, qos=0):
    """Publish a message. :param qos int: 0 or 1"""
    return _inst().publish(topic, payload, qos)


def subscribe(topic, callback, qos=0):
    """Subscribe to a topic."""
    return _inst().subscribe_topic(topic, callback, qos)


def unsubscribe(topic):
    """Unsubscribe from a topic."""
    return _inst().unsubscribe_topic(topic)


def is_connected():
    """Check MQTT connection status."""
    return _inst().is_connected()


def disconnect():
    """Disconnect from MQTT broker."""
    return _inst().disconnect()


def ping():
    """
    Return pong. Call via MQTT: {devfid}/sim800mqtt/ping
    Response arrives on {devfid}/sim800mqtt/ping/response
    :return str: pong
    """
    return 'pong'


#######################
# LM helper functions #
#######################

def pinmap():
    """[i] micrOS LM naming convention"""
    return pinmap_search(['sim800_tx', 'sim800_rx'])


def help(widgets=False):
    """[i] micrOS LM naming convention - built-in help message"""
    return resolve((
        'load pin_code apn server="broker" port=1883 user="u" password="p" tx_pin=16 rx_pin=17',
        'unload',
        'publish topic="t" payload="msg" qos=0',
        'subscribe topic="t" callback=<func> qos=0',
        'unsubscribe topic="t"',
        'is_connected',
        'disconnect',
        'ping',
        'pinmap',
    ), widgets=widgets)
