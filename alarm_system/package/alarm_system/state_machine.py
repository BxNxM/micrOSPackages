"""State machine and zone trigger logic for alarm_system."""
import time
import json
from Common import micro_task, console
from Notify import Notify

# States
DISARMED = 'DISARMED'
ARMING = 'ARMING'
ARMED = 'ARMED'
ENTRY_DELAY = 'ENTRY_DELAY'
ALARM = 'ALARM'

VALID_STATES = (DISARMED, ARMING, ARMED, ENTRY_DELAY, ALARM)
VALID_TYPES = ('delayed', 'instant', '24h', 'cross')
VALID_GROUPS = ('perimeter', 'interior', 'always')

# Module state
state = DISARMED
arm_mode = None
delay_task = None
alarm_memory = []
chime = False
auto_arm_delay = None
auto_arm_mode = 'full'
auto_arm_task = None
last_activity = 0
bypassed = set()
exit_delay = 30
entry_delay = 15
zones = {}

# Action hooks (set by LM during init)
_action_hooks = {}


def set_action_hooks(hooks):
    global _action_hooks
    _action_hooks = hooks


def transition_to(new_state):
    global state
    prev = state
    state = new_state
    from alarm_system.config import save_state
    save_state(state, arm_mode)
    console(f"alarm_system: {prev} -> {new_state}")
    Notify.notify(json.dumps({"state": new_state, "prev": prev, "mode": arm_mode}), topic="alarm/state/change")
    _action_hooks.get(new_state, lambda: None)()


def do_arm(mode='full', force=False):
    global arm_mode, delay_task, alarm_memory
    if state != DISARMED:
        return f"Cannot arm: current state is {state}"

    open_tamper = [n for n, z in zones.items()
                   if z['type'] == '24h' and z.get('last_event') == 'triggered']
    if open_tamper:
        return f"Cannot arm: tamper zone open: {', '.join(open_tamper)}"

    trouble = get_trouble_zones()
    if trouble and not force:
        return f"Cannot arm: trouble zones: {', '.join(trouble)}"

    open_z = [n for n, z in zones.items()
              if z.get('last_event') == 'triggered'
              and z['type'] != '24h'
              and is_group_active_for_mode(z['group'], mode)]
    if open_z and not force:
        return f"Cannot arm: open zones: {', '.join(open_z)}"

    alarm_memory = []
    arm_mode = mode
    transition_to(ARMING)
    delay_task = micro_task(tag="alarm_exit_delay", task=_exit_delay_task())
    from alarm_system.event_log import log as elog
    elog('arm', {'mode': mode, 'force': force, 'bypassed': open_z if open_z else None})
    return f"Arming ({mode}), exit delay {exit_delay}s"


def do_disarm():
    global arm_mode, delay_task
    prev = state
    arm_mode = None
    delay_task = None
    bypassed.clear()
    transition_to(DISARMED)
    reset_activity()
    from alarm_system.event_log import log as elog
    elog('disarm', {'from_state': prev})
    return "Disarmed"


def handle_zone_trigger(name, event):
    global delay_task
    if name not in zones:
        return f"Unknown zone: {name}"

    zone = zones[name]
    zone['last_event'] = event

    if 'supervision' in zone:
        zone['last_seen'] = time.time()

    if event != 'triggered':
        return f"Zone {name} reset"

    zone_type = zone['type']
    zone_group = zone['group']

    if chime and state == DISARMED and zone_type == 'delayed':
        Notify.notify(json.dumps({"action": "chime", "zone": name}), topic="alarm/chime/event")

    if state == DISARMED:
        reset_activity()

    from alarm_system.event_log import log as elog

    # 24h zones
    if zone_type == '24h':
        if state in (ARMED, ENTRY_DELAY):
            alarm_memory.append(name)
            elog('alarm', {'zone': name, 'type': '24h'})
            transition_to(ALARM)
            return f"ALARM: 24h zone {name} triggered"
        else:
            elog('silent_alert', {'zone': name, 'state': state})
            from alarm_system.actions import on_silent_alert
            on_silent_alert(name)
            return f"Silent alert: 24h zone {name} triggered while {state}"

    if state != ARMED:
        return f"Ignored: zone {name} triggered while {state}"

    if name in bypassed:
        return f"Ignored: zone {name} is bypassed"

    if not is_group_active(zone_group):
        return f"Ignored: zone {name} group '{zone_group}' not active in mode '{arm_mode}'"

    if zone_type == 'delayed':
        alarm_memory.append(name)
        elog('zone_trigger', {'zone': name, 'type': 'delayed', 'result': 'entry_delay'})
        transition_to(ENTRY_DELAY)
        delay_task = micro_task(tag="alarm_entry_delay", task=_entry_delay_task())
        return f"Entry delay: zone {name} triggered"

    if zone_type == 'instant':
        alarm_memory.append(name)
        elog('alarm', {'zone': name, 'type': 'instant'})
        transition_to(ALARM)
        return f"ALARM: instant zone {name} triggered"

    if zone_type == 'cross':
        pair_name = zone.get('cross_pair')
        window = zone.get('cross_window', 30)
        zone['last_trigger_time'] = time.time()
        pair = zones.get(pair_name)
        if pair and pair.get('last_trigger_time'):
            elapsed = time.time() - pair['last_trigger_time']
            if elapsed <= window:
                alarm_memory.append(name)
                alarm_memory.append(pair_name)
                elog('alarm', {'zone': name, 'type': 'cross', 'pair': pair_name})
                transition_to(ALARM)
                return f"ALARM: cross-zone {name}+{pair_name}"
        return f"Cross-zone: {name} triggered, waiting for pair"

    return f"Unknown zone type: {zone_type}"


# Helpers

def is_group_active(group):
    return is_group_active_for_mode(group, arm_mode)


def is_group_active_for_mode(group, mode):
    if group == 'always':
        return True
    if mode == 'full' and group in ('perimeter', 'interior'):
        return True
    if mode == 'night' and group == 'perimeter':
        return True
    return False


def get_trouble_zones():
    now = time.time()
    trouble = []
    for name, z in zones.items():
        timeout = z.get('supervision')
        if timeout and (now - z.get('last_seen', 0)) > timeout:
            trouble.append(name)
    return trouble


def reset_activity():
    global last_activity, auto_arm_task
    last_activity = time.time()
    if auto_arm_delay and state == DISARMED:
        auto_arm_task = None
        auto_arm_task = micro_task(tag="alarm_auto_arm", task=_auto_arm_timer())


# Async tasks

async def _detection_loop(interval):
    with micro_task(tag="alarm_detection_task") as my_task:
        while True:
            for zone in zones.values():
                sensor = zone.get('sensor')
                if sensor:
                    sensor.process_if_needed()
                    sensor.poll()
            await my_task.feed(sleep_ms=interval)


async def _exit_delay_task():
    with micro_task(tag="alarm_exit_delay") as my_task:
        await my_task.feed(sleep_ms=exit_delay * 1000)
        if state == ARMING:
            transition_to(ARMED)


async def _entry_delay_task():
    with micro_task(tag="alarm_entry_delay") as my_task:
        await my_task.feed(sleep_ms=entry_delay * 1000)
        if state == ENTRY_DELAY:
            transition_to(ALARM)


async def _auto_arm_timer():
    with micro_task(tag="alarm_auto_arm") as my_task:
        await my_task.feed(sleep_ms=auto_arm_delay * 1000)
        if state == DISARMED and auto_arm_delay:
            elapsed = time.time() - last_activity
            if elapsed >= auto_arm_delay - 1:
                from alarm_system.event_log import log as elog
                elog('auto_arm', {'delay': auto_arm_delay, 'mode': auto_arm_mode})
                do_arm(mode=auto_arm_mode)
