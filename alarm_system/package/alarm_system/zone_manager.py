"""Zone and sensor management for alarm_system."""
import time
from Common import console
from alarm_system.state_machine import zones, VALID_TYPES, VALID_GROUPS, handle_zone_trigger


def create_sensor(name, pin, type, group, invert=False):
    from alarm_system.door_sensor import DebouncedInput
    sensor = DebouncedInput(pin, name, callback=handle_zone_trigger, invert=invert)
    zones[name] = {'type': type, 'group': group, 'last_event': 'ok', 'pin': pin, 'invert': invert, 'sensor': sensor}


def add_sensor(name, pin, type='delayed', group='perimeter', invert=False):
    if name in zones:
        return f"Zone '{name}' already exists. Remove it first."
    if type not in VALID_TYPES:
        return f"Invalid type '{type}'. Must be one of: {', '.join(VALID_TYPES)}"
    if group not in VALID_GROUPS:
        return f"Invalid group '{group}'. Must be one of: {', '.join(VALID_GROUPS)}"
    create_sensor(name, pin, type, group, invert)
    from alarm_system.config import save_config
    from alarm_system.state_machine import exit_delay, entry_delay, zones as z
    save_config(z, exit_delay, entry_delay, 50, 100)
    return f"Sensor '{name}' added: pin={pin}, type={type}, group={group}, invert={invert}"


def remove_sensor(name):
    if name not in zones:
        return f"Sensor '{name}' not found."
    zone = zones[name]
    if 'sensor' not in zone:
        return f"'{name}' is a remote zone, use remove_zone."
    zone['sensor'].pin.irq(handler=None)
    del zones[name]
    from alarm_system.config import save_config
    from alarm_system.state_machine import exit_delay, entry_delay
    save_config(zones, exit_delay, entry_delay, 50, 100)
    return f"Sensor '{name}' removed."


def add_zone(name, type='instant', group='perimeter', cross_pair=None, cross_window=30):
    if name in zones:
        return f"Zone '{name}' already exists. Remove it first."
    if type not in VALID_TYPES:
        return f"Invalid type '{type}'. Must be one of: {', '.join(VALID_TYPES)}"
    if group not in VALID_GROUPS:
        return f"Invalid group '{group}'. Must be one of: {', '.join(VALID_GROUPS)}"
    if type == 'cross' and not cross_pair:
        return "Cross-zone requires 'cross_pair' parameter."
    zone = {'type': type, 'group': group, 'last_event': 'ok'}
    if type == 'cross':
        zone['cross_pair'] = cross_pair
        zone['cross_window'] = cross_window
    zones[name] = zone
    from alarm_system.config import save_config
    from alarm_system.state_machine import exit_delay, entry_delay
    save_config(zones, exit_delay, entry_delay, 50, 100)
    return f"Zone '{name}' added: type={type}, group={group}"


def remove_zone(name):
    if name not in zones:
        return f"Zone '{name}' not found."
    if 'sensor' in zones[name]:
        return f"'{name}' is a local sensor, use remove_sensor."
    del zones[name]
    from alarm_system.config import save_config
    from alarm_system.state_machine import exit_delay, entry_delay
    save_config(zones, exit_delay, entry_delay, 50, 100)
    return f"Zone '{name}' removed."


def list_zones():
    return {name: {
        'type': z['type'], 'group': z['group'],
        'pin': z.get('pin'), 'last_event': z.get('last_event', 'ok')
    } for name, z in zones.items()}


def bypass_zone(name):
    from alarm_system.state_machine import bypassed
    if name not in zones:
        return f"Zone '{name}' not found."
    if zones[name]['type'] == '24h':
        return f"Cannot bypass 24h zone '{name}'."
    bypassed.add(name)
    from alarm_system.event_log import log as elog
    elog('bypass', {'zone': name})
    return f"Zone '{name}' bypassed."


def unbypass_zone(name):
    from alarm_system.state_machine import bypassed
    if name not in bypassed:
        return f"Zone '{name}' is not bypassed."
    bypassed.discard(name)
    return f"Zone '{name}' unbypass."


def supervise_zone(name, timeout=600):
    if name not in zones:
        return f"Zone '{name}' not found."
    if 'pin' in zones[name]:
        return f"Cannot supervise local GPIO zone '{name}'."
    zones[name]['supervision'] = timeout
    zones[name]['last_seen'] = time.time()
    from alarm_system.config import save_config
    from alarm_system.state_machine import exit_delay, entry_delay
    save_config(zones, exit_delay, entry_delay, 50, 100)
    return f"Zone '{name}' supervised: timeout={timeout}s"


def unsupervise_zone(name):
    if name not in zones:
        return f"Zone '{name}' not found."
    zones[name].pop('supervision', None)
    zones[name].pop('last_seen', None)
    from alarm_system.config import save_config
    from alarm_system.state_machine import exit_delay, entry_delay
    save_config(zones, exit_delay, entry_delay, 50, 100)
    return f"Zone '{name}' supervision removed."
