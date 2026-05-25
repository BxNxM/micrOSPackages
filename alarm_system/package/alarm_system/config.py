"""Config and state persistence for alarm_system."""
import json
from Common import console, data_dir

_config_file = None
_state_file = None


def init(config_filename, state_filename='alarm_state.json'):
    global _config_file, _state_file
    _config_file = data_dir(config_filename)
    _state_file = data_dir(state_filename)


def save_config(zones, exit_delay, entry_delay, interval, max_log_entries):
    if _config_file is None:
        return
    sensors = []
    zone_list = []
    for name, z in zones.items():
        entry = {'name': name, 'type': z['type'], 'group': z['group']}
        if 'pin' in z:
            entry['pin'] = z['pin']
            if z.get('invert'):
                entry['invert'] = True
            sensors.append(entry)
        else:
            if z['type'] == 'cross':
                entry['cross_pair'] = z.get('cross_pair')
                entry['cross_window'] = z.get('cross_window', 30)
            if 'supervision' in z:
                entry['supervision'] = z['supervision']
            zone_list.append(entry)
    try:
        from alarm_system.mqtt_watcher import get_watches_config
        watches = get_watches_config()
    except Exception:
        watches = []
    config = {
        'exit_delay': exit_delay,
        'entry_delay': entry_delay,
        'interval': interval,
        'max_log_entries': max_log_entries,
        'sensors': sensors,
        'zones': zone_list,
        'watches': watches
    }
    try:
        with open(_config_file, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        console(f"alarm_system: save config error: {e}")


def load_config():
    if _config_file is None:
        return None
    try:
        with open(_config_file, 'r') as f:
            return json.load(f)
    except (OSError, ValueError, Exception):
        return None


def save_state(state, arm_mode):
    if _state_file is None:
        return
    try:
        with open(_state_file, 'w') as f:
            json.dump({'state': state, 'arm_mode': arm_mode}, f)
    except Exception as e:
        console(f"alarm_system: save state error: {e}")


def load_state():
    from alarm_system.state_machine import DISARMED, ARMING, ENTRY_DELAY, ALARM, ARMED, VALID_STATES
    if _state_file is None:
        return DISARMED, None
    try:
        with open(_state_file, 'r') as f:
            data = json.load(f)
        s = data.get('state', DISARMED)
        m = data.get('arm_mode', None)
        if s == ARMING:
            s = ARMED
        elif s == ENTRY_DELAY:
            s = ALARM
        elif s not in VALID_STATES:
            s = DISARMED
        return s, m
    except (OSError, ValueError, Exception):
        return DISARMED, None
