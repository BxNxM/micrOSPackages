"""
Pump actuator and watering-task helpers for Aqua.
"""

try:
    import utime as time
except Exception:
    import time

try:
    from machine import Pin
except Exception:
    Pin = None

from Common import manage_task, micro_task
from microIO import bind_pin, pinmap_search
from irrigation_system import monitoring


RUNTIME = {
    "pump_on": False,
    "last_action": "boot",
    "last_run": None,
    "watering": None,
}

PUMP_TAG = "aqua_pump"
TASK_TAG = "aqua._watering_task"
_PUMP_PIN = None
_PUMP_OUT = None


def now():
    try:
        return int(time.time())
    except Exception:
        return 0


def ticks_ms():
    try:
        return time.ticks_ms()
    except Exception:
        return int(time.time() * 1000)


def ticks_diff(current, start):
    try:
        return time.ticks_diff(current, start)
    except Exception:
        return current - start


def set_last_action(action):
    RUNTIME["last_action"] = action


def bind_pump(config=None, pump_pin=None):
    global _PUMP_PIN, _PUMP_OUT
    config = monitoring.CONFIG if config is None else config
    if pump_pin is not None:
        config["pump_pin"] = monitoring.as_int(pump_pin, config.get("pump_pin"), 0, None)
    if _PUMP_PIN is None:
        pin = monitoring.as_int(config.get("pump_pin"), 26, minimum=0)
        _PUMP_PIN = bind_pin(PUMP_TAG, pin)
    if _PUMP_OUT is None and Pin is not None:
        _PUMP_OUT = Pin(_PUMP_PIN, Pin.OUT)
        _PUMP_OUT.value(0)
    RUNTIME["pump_pin"] = _PUMP_PIN
    RUNTIME["pump_level"] = 1 if RUNTIME.get("pump_on") else 0
    RUNTIME["pump_hw"] = _PUMP_OUT is not None
    return _PUMP_PIN


def set_pump_power(enabled, config=None):
    bind_pump(config=config)
    level = 1 if enabled else 0
    if _PUMP_OUT is not None:
        _PUMP_OUT.value(level)
    RUNTIME["pump_level"] = level
    RUNTIME["pump_on"] = bool(enabled)
    return level


def pinmap(config=None):
    config = monitoring.CONFIG if config is None else config
    pins = pinmap_search(PUMP_TAG)
    if pins.get(PUMP_TAG) is None:
        pins[PUMP_TAG] = config.get("pump_pin")
    return pins


def run_state(run_plan, started_ms, active=True, complete=False):
    duration_s = monitoring.as_float(run_plan.get("duration_s"), 0, minimum=0)
    target_l = monitoring.as_float(run_plan.get("volume_l"), 0, minimum=0)
    heads = monitoring.as_int(run_plan.get("head_count"), 1, minimum=1)
    elapsed_s = duration_s if complete else max(0, ticks_diff(ticks_ms(), started_ms) / 1000.0)
    if duration_s > 0:
        elapsed_s = min(duration_s, elapsed_s)
        ratio = elapsed_s / duration_s
    else:
        ratio = 1 if complete else 0
    remaining_s = max(0, duration_s - elapsed_s)
    dispensed_l = target_l * ratio
    return {
        "task": TASK_TAG,
        "active": bool(active and remaining_s > 0),
        "started": RUNTIME.get("last_run", {}).get("time") if isinstance(RUNTIME.get("last_run"), dict) else None,
        "started_ms": started_ms,
        "duration_s": round(duration_s, 1),
        "elapsed_s": round(elapsed_s, 1),
        "remaining_s": round(remaining_s, 1),
        "target_l": round(target_l, 3),
        "dispensed_l": round(dispensed_l, 3),
        "per_head_l": round(target_l / heads, 3),
        "per_head_dispensed_l": round(dispensed_l / heads, 3),
        "progress_percent": round(ratio * 100.0, 1),
    }


def task_message(run):
    if run.get("active"):
        return "Watering: {}/{} L, {} s left".format(
            run.get("dispensed_l"), run.get("target_l"), run.get("remaining_s")
        )
    if run.get("error"):
        return "Watering error: {}".format(run.get("error"))
    return "Watering done: {}/{} L".format(run.get("dispensed_l"), run.get("target_l"))


def set_task_out(run):
    RUNTIME["task_out"] = task_message(run)
    return RUNTIME["task_out"]


def finish_watering(run_plan=None, started_ms=None, complete=False, error=None):
    if run_plan is None and isinstance(RUNTIME.get("last_run"), dict):
        run_plan = RUNTIME["last_run"].get("plan")
    if not isinstance(run_plan, dict):
        run_plan = {}
    if started_ms is None and isinstance(RUNTIME.get("watering"), dict):
        started_ms = RUNTIME["watering"].get("started_ms")
    if started_ms is None:
        started_ms = ticks_ms()
    run = run_state(run_plan, started_ms, active=False, complete=complete)
    if error is not None:
        run["error"] = str(error)
    set_pump_power(False)
    RUNTIME["watering"] = run
    RUNTIME["last_action"] = "water_error" if error is not None else ("water_done" if complete else "water_stopped")
    set_task_out(run)
    if isinstance(RUNTIME.get("last_run"), dict):
        RUNTIME["last_run"]["result"] = run
    return run


def refresh_watering():
    run = RUNTIME.get("watering")
    if not RUNTIME.get("pump_on") or not isinstance(run, dict):
        return run
    if not isinstance(RUNTIME.get("last_run"), dict):
        return run
    plan_data = RUNTIME["last_run"].get("plan")
    if not isinstance(plan_data, dict):
        return run
    started_ms = run.get("started_ms")
    if started_ms is None:
        return run
    run = run_state(plan_data, started_ms)
    if run.get("remaining_s") <= 0:
        return finish_watering(plan_data, started_ms, complete=True)
    RUNTIME["watering"] = run
    set_task_out(run)
    return run


@micro_task("aqua", _wrap=True)
async def watering_task(tag, run_plan, started_ms):
    completed = False
    error = None
    with micro_task(tag=tag) as my_task:
        try:
            while True:
                run = run_state(run_plan, started_ms)
                RUNTIME["watering"] = run
                my_task.out = set_task_out(run)
                if run.get("remaining_s") <= 0:
                    completed = True
                    break
                sleep_ms = int(min(1000, max(100, run.get("remaining_s") * 1000)))
                await my_task.feed(sleep_ms=sleep_ms)
        except Exception as e:
            if RUNTIME.get("pump_on"):
                error = e
        finally:
            final = finish_watering(run_plan, started_ms, complete=completed, error=error)
            my_task.out = set_task_out(final)


def task_status():
    task = micro_task(TASK_TAG)
    if task is None:
        return {"id": TASK_TAG, "active": False, "out": RUNTIME.get("task_out")}
    try:
        active = not task.done.is_set()
    except Exception:
        active = RUNTIME.get("pump_on")
    return {"id": TASK_TAG, "active": bool(active), "out": getattr(task, "out", RUNTIME.get("task_out"))}


def load(config=None, pump_pin=None):
    bind_pump(config=config, pump_pin=pump_pin)
    RUNTIME["last_action"] = "load"
    return RUNTIME["pump_pin"]


def water(config, volume_l=None, per_head_l=None):
    if RUNTIME.get("pump_on"):
        refresh_watering()
        return {
            "state": False,
            "error": "already_watering",
            "run": RUNTIME.get("watering"),
            "task": task_status(),
        }
    run_plan = monitoring.plan(volume_l=volume_l, per_head_l=per_head_l)
    if run_plan["volume_l"] <= 0:
        RUNTIME["last_action"] = "water_blocked"
        return {"state": False, "error": "missing_volume", "plan": run_plan, "ready": monitoring.ready()}
    safety = monitoring.ready(required_l=run_plan["volume_l"])
    if not safety["ok"]:
        RUNTIME["last_action"] = "water_blocked"
        return {"state": False, "error": "safety_lockout", "plan": run_plan, "ready": safety}
    started_ms = ticks_ms()
    set_pump_power(True, config)
    RUNTIME["last_action"] = "water"
    RUNTIME["last_run"] = {"time": now(), "plan": run_plan}
    RUNTIME["watering"] = run_state(run_plan, started_ms)
    task_state = watering_task(run_plan, started_ms)
    RUNTIME["last_run"]["task"] = task_state
    set_task_out(RUNTIME["watering"])
    return {"state": True, "plan": run_plan, "ready": safety, "run": RUNTIME["watering"], "task": task_state}


def stop():
    if RUNTIME.get("pump_on"):
        manage_task(TASK_TAG, "kill")
        finish_watering(complete=False)
    else:
        set_pump_power(False)
    RUNTIME["last_action"] = "stop"
    return status()


def start(config=None):
    set_pump_power(True, config)
    RUNTIME["last_action"] = "start"
    return status()


def status():
    refresh_watering()
    return {
        "pump_on": RUNTIME.get("pump_on"),
        "runtime": RUNTIME,
        "task": task_status(),
    }
