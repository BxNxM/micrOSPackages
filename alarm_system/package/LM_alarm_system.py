"""LM_alarm_system.py — Alarm panel interface for micrOS."""
from Common import micro_task, console, data_dir
from microIO import pinmap_search
from Types import resolve
import time

_BOOK = 'alarm'


def load(config='alarm_config.json'):
    from alarm_system import state_machine as sm
    from alarm_system import config as cfg
    from alarm_system.zone_manager import create_sensor

    cfg.init(config)
    c = cfg.load_config()
    if c:
        sm.exit_delay = c.get('exit_delay', 30)
        sm.entry_delay = c.get('entry_delay', 15)
        interval = c.get('interval', 50)
        max_log = c.get('max_log_entries', 100)
        for s in c.get('sensors', []):
            create_sensor(s['name'], s['pin'], s['type'], s['group'], s.get('invert', False))
        for z in c.get('zones', []):
            zone = {'type': z['type'], 'group': z['group'], 'last_event': 'ok'}
            if z['type'] == 'cross':
                zone['cross_pair'] = z.get('cross_pair')
                zone['cross_window'] = z.get('cross_window', 30)
            if 'supervision' in z:
                zone['supervision'] = z['supervision']
                zone['last_seen'] = time.time()
            sm.zones[z['name']] = zone
        from alarm_system.mqtt_watcher import init as wi, load_watches
        wi(sm.handle_zone_trigger)
        load_watches(c.get('watches', []))
    else:
        interval = 50
        max_log = 100

    from alarm_system.event_log import init as li
    li(data_dir('alarm_log.json'), max_log)

    phonebook = c.get('phonebook', 'alarm_users.json') if c else 'alarm_users.json'
    try:
        import LM_users as users
        users.load(json_file=phonebook, book=_BOOK)
    except Exception:
        pass

    try:
        import LM_sim800 as sim
        from alarm_system.sms_handler import init as si, handle_sms
        import sys
        si(sys.modules[__name__])
        sim.subscribe('sms', handle_sms)
    except Exception:
        pass

    from alarm_system.actions import on_arming, on_armed, on_entry_delay, on_disarmed
    def _on_alarm():
        from alarm_system.actions import on_alarm
        on_alarm(sm.alarm_memory)
    sm.set_action_hooks({
        'ARMING': on_arming, 'ARMED': on_armed,
        'ENTRY_DELAY': on_entry_delay, 'ALARM': _on_alarm,
        'DISARMED': on_disarmed
    })

    sm.state, sm.arm_mode = cfg.load_state()
    micro_task(tag="alarm_detection_task", task=sm._detection_loop(interval))

    from alarm_system.event_log import log as elog
    elog('system_start', {'state': sm.state, 'mode': sm.arm_mode, 'zones': len(sm.zones)})
    return f"Alarm system started. State: {sm.state}, zones: {len(sm.zones)}"


def unload():
    from alarm_system import state_machine as sm
    try:
        from alarm_system.event_log import log as elog
        elog('system_stop')
    except Exception:
        pass
    try:
        import LM_sim800 as sim
        from alarm_system.sms_handler import handle_sms
        sim.unsubscribe('sms', handle_sms)
    except Exception:
        pass
    for z in sm.zones.values():
        s = z.get('sensor')
        if s:
            s.pin.irq(handler=None)
    sm.zones.clear()
    sm.delay_task = None
    try:
        from alarm_system.mqtt_watcher import unload as wu
        wu()
    except Exception:
        pass
    return 'Alarm system stopped.'


def status():
    from alarm_system.state_machine import state, arm_mode, zones, alarm_memory, bypassed, get_trouble_zones
    return {
        'state': state, 'arm_mode': arm_mode,
        'zones': {n: {'type': z['type'], 'group': z['group'], 'last_event': z.get('last_event', 'ok')} for n, z in zones.items()},
        'open_zones': [n for n, z in zones.items() if z.get('last_event') == 'triggered'],
        'alarm_memory': list(alarm_memory),
        'bypassed': list(bypassed),
        'trouble': get_trouble_zones()
    }


def arm(mode='full', force=False):
    from alarm_system.state_machine import do_arm
    return do_arm(mode, force)


def disarm():
    from alarm_system.state_machine import do_disarm
    return do_disarm()


def zone_trigger(name, event):
    from alarm_system.state_machine import handle_zone_trigger
    return handle_zone_trigger(name, event)


def add_sensor(name, pin, type='delayed', group='perimeter', invert=False):
    from alarm_system.zone_manager import add_sensor as _add
    return _add(name, pin, type, group, invert)


def remove_sensor(name):
    from alarm_system.zone_manager import remove_sensor as _rm
    return _rm(name)


def add_zone(name, type='instant', group='perimeter', cross_pair=None, cross_window=30):
    from alarm_system.zone_manager import add_zone as _add
    return _add(name, type, group, cross_pair, cross_window)


def remove_zone(name):
    from alarm_system.zone_manager import remove_zone as _rm
    return _rm(name)


def list_zones():
    from alarm_system.zone_manager import list_zones as _lz
    return _lz()


def show_config():
    from alarm_system.config import load_config
    c = load_config()
    return c if c else "No config file found."


def add_watch(topic, zone, trigger_value, reset_value=None, trigger_field=None):
    from alarm_system.state_machine import zones
    if zone not in zones:
        zones[zone] = {'type': 'instant', 'group': 'perimeter', 'last_event': 'ok'}
    from alarm_system.mqtt_watcher import add_watch as _aw
    r = _aw(topic, zone, trigger_value, reset_value, trigger_field)
    from alarm_system.config import save_config
    from alarm_system.state_machine import exit_delay, entry_delay
    save_config(zones, exit_delay, entry_delay, 50, 100)
    return r


def remove_watch(topic):
    from alarm_system.mqtt_watcher import remove_watch as _rw
    r = _rw(topic)
    from alarm_system.config import save_config
    from alarm_system.state_machine import zones, exit_delay, entry_delay
    save_config(zones, exit_delay, entry_delay, 50, 100)
    return r


def list_watches():
    from alarm_system.mqtt_watcher import list_watches as _lw
    return _lw()


def event_log(count=20):
    from alarm_system.event_log import get
    return get(count)


def clear_log():
    from alarm_system.event_log import clear
    clear()
    return 'Event log cleared.'


def alarm_memory():
    from alarm_system.state_machine import alarm_memory as am
    return list(am)


def chime(state=None):
    from alarm_system import state_machine as sm
    if state is None:
        return f"Chime: {'on' if sm.chime else 'off'}"
    if state == 'on':
        sm.chime = True
        return 'Chime enabled.'
    elif state == 'off':
        sm.chime = False
        return 'Chime disabled.'
    return f"Invalid state '{state}'. Use 'on' or 'off'."


def auto_arm(delay=None, mode='full'):
    from alarm_system import state_machine as sm
    if delay is None or delay == 0:
        sm.auto_arm_delay = None
        sm.auto_arm_task = None
        return 'Auto-arm disabled.'
    sm.auto_arm_delay = delay
    sm.auto_arm_mode = mode
    sm.reset_activity()
    return f"Auto-arm enabled: {delay}s inactivity -> arm({mode})"


def bypass(name):
    from alarm_system.zone_manager import bypass_zone
    return bypass_zone(name)


def unbypass(name):
    from alarm_system.zone_manager import unbypass_zone
    return unbypass_zone(name)


def supervise(name, timeout=600):
    from alarm_system.zone_manager import supervise_zone
    return supervise_zone(name, timeout)


def unsupervise(name):
    from alarm_system.zone_manager import unsupervise_zone
    return unsupervise_zone(name)


def pinmap():
    from alarm_system.state_machine import zones
    pins = [f"alarm_{n}" for n, z in zones.items() if 'pin' in z]
    return pinmap_search(pins) if pins else {}


def help(widgets=False):
    return resolve((
        'load config="alarm_config.json"', 'unload',
        'arm mode="full"', 'arm mode="full" force=True', 'arm mode="night"',
        'disarm', 'status',
        'add_sensor name="door" pin=19 type="delayed" group="perimeter"',
        'add_sensor name="door" pin=19 type="delayed" group="perimeter" invert=True',
        'remove_sensor name="door"',
        'add_zone name="light" type="instant" group="interior"',
        'remove_zone name="light"', 'list_zones',
        'zone_trigger name="door" event="triggered"', 'show_config',
        'add_watch topic="zigbee2mqtt/sensor" zone="window" trigger_field="contact" trigger_value=false reset_value=true',
        'remove_watch topic="zigbee2mqtt/sensor"', 'list_watches',
        'event_log count=20', 'clear_log', 'alarm_memory',
        'chime state="on"', 'chime state="off"',
        'auto_arm delay=3600 mode="night"', 'auto_arm delay=0',
        'bypass name="window"', 'unbypass name="window"',
        'supervise name="window" timeout=600', 'unsupervise name="window"',
        'pinmap'), widgets=widgets)
