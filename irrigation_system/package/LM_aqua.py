"""
Aqua irrigation skeleton for micrOS.

The load module keeps only public command and web endpoint glue. Monitoring
calculations live in irrigation_system.monitoring and pump/task handling lives
in irrigation_system.actuators.
"""

try:
    import ujson as json
except Exception:
    import json

from Common import web_endpoint
from Types import resolve
from irrigation_system import actuators, monitoring


_WEB_READY = False


def _json(data):
    return "application/json", json.dumps(data)


def _api_get(*_):
    return _json(status(measure=True))


def _api_post(_, body):
    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except Exception as e:
        return _json({"state": False, "error": "invalid_json", "detail": str(e)})

    action = payload.get("action", "status")
    if action == "configure":
        return _json(configure(**payload.get("config", {})))
    if action == "water":
        return _json(water(**payload.get("run", {})))
    if action == "stop":
        return _json(stop())
    if action == "set_level":
        return _json(set_level(**payload.get("level", {})))
    if action == "measure_level":
        level = payload.get("level", {})
        if not isinstance(level, dict):
            level = {}
        level["measure"] = True
        return _json(set_level(**level))
    if action == "status":
        return _json(status(measure=True))
    return _json({"state": False, "error": "unknown_action", "action": action})


def _register_web():
    global _WEB_READY
    if _WEB_READY:
        return True
    web_endpoint("aqua/ui", "irrigation_system/aqua.html")
    web_endpoint("aqua/api", _api_get)
    web_endpoint("aqua/api", _api_post, "POST")
    _WEB_READY = True
    return True


def _dashboard_state(measure=False):
    monitor = monitoring.status(measure=measure)
    pump = actuators.status()
    runtime = dict(pump["runtime"])
    runtime["last_level"] = monitor["level_sensor"]
    return {
        "state": "watering" if pump["pump_on"] else "idle",
        "pump_on": pump["pump_on"],
        "config": monitor["config"],
        "tank": monitor["tank"],
        "flow": monitor["flow"],
        "soil": monitor["soil"],
        "ready": monitor["ready"],
        "runtime": runtime,
        "level_sensor": monitor["level_sensor"],
        "task": pump["task"],
        "endpoints": {
            "ui": "/aqua/ui",
            "api": "/aqua/api",
        },
    }


def load(web=True, pump_pin=None):
    """
    Register the Aqua dashboard and book the pump pin.
    """
    actuators.load(monitoring.CONFIG, pump_pin=pump_pin)
    if web:
        _register_web()
    return "Aqua irrigation system loaded. Endpoints: /aqua/ui and /aqua/api"


def configure(tank_width_cm=None, tank_depth_cm=None, tank_height_cm=None,
              water_distance_cm=None, min_level_percent=None, pump_l_hour=None,
              head_count=None, soil_sensor_count=None, pump_pin=None,
              level_module=None, **_):
    """
    Update dashboard configuration values.
    """
    was_manual = monitoring.is_manual_level_module()
    monitoring.update_config({
        "tank_width_cm": tank_width_cm,
        "tank_depth_cm": tank_depth_cm,
        "tank_height_cm": tank_height_cm,
        "water_distance_cm": water_distance_cm,
        "min_level_percent": min_level_percent,
        "pump_l_hour": pump_l_hour,
        "head_count": head_count,
        "soil_sensor_count": soil_sensor_count,
        "pump_pin": pump_pin,
        "level_module": level_module,
    })
    monitoring.configure_level(was_manual, water_distance_cm=water_distance_cm)
    actuators.set_last_action("configure")
    return status()


def tank():
    """
    Return tank level and volume.
    """
    return monitoring.tank()


def flow():
    """
    Return pump and irrigation-head flow calculations.
    """
    return monitoring.flow()


def pinmap():
    """
    Shows logical pins used by this Load Module.
    """
    return actuators.pinmap(monitoring.CONFIG)


def soil():
    """
    Return soil moisture sensor readings.
    """
    return monitoring.soil()


def plan(volume_l=None, per_head_l=None):
    """
    Preview a watering run from total or per-head volume.
    """
    return monitoring.plan(volume_l=volume_l, per_head_l=per_head_l)


def ready(volume_l=None):
    """
    Return readiness based on tank level and requested volume.
    """
    return monitoring.ready(required_l=volume_l)


def water(volume_l=None, per_head_l=None, **_):
    """
    Start a calculated watering run.
    """
    return actuators.water(monitoring.CONFIG, volume_l=volume_l, per_head_l=per_head_l)


def stop():
    """
    Stop the active watering task.
    """
    actuators.stop()
    return status()


def on():
    """
    Dummy manual pump-on command.
    """
    actuators.on(monitoring.CONFIG)
    return status()


def off():
    """
    Dummy manual pump-off command.
    """
    return stop()


def sensor_distance(module=None):
    """
    Read top-to-water distance from the configured ultrasonic distance module.
    """
    return monitoring.sensor_distance(module=module)


def set_level(distance_cm=None, distance_mm=None, measure=False, module=None, clear=False, **_):
    """
    Update top-to-water distance in manual mode or by sensor measurement.
    """
    result = monitoring.set_level(
        distance_cm=distance_cm,
        distance_mm=distance_mm,
        measure=measure,
        module=module,
        clear=clear,
    )
    if isinstance(result, dict) and result.get("state") is False and result.get("source") != "manual":
        actuators.set_last_action("set_level_failed")
        return result
    actuators.set_last_action("set_level")
    return result


def status(measure=False):
    """
    Return the complete dashboard state.
    """
    return _dashboard_state(measure=measure)


def help(widgets=False):
    """
    micrOS LM help.
    """
    return resolve((
        "load web=True pump_pin=None",
        "STATUS status",
        "TEXTBOX tank",
        "TEXTBOX flow",
        "pinmap",
        "TEXTBOX soil",
        "TEXTBOX sensor_distance module=None",
        "plan volume_l=1 per_head_l=None",
        "water volume_l=1 per_head_l=None",
        "BUTTON stop",
        "BUTTON on",
        "BUTTON off",
        "configure tank_width_cm=40 tank_depth_cm=25 tank_height_cm=20 water_distance_cm=7 level_module=manual pump_l_hour=300 head_count=4 soil_sensor_count=4 pump_pin=26",
        "set_level distance_cm=7 distance_mm=None measure=False module=None clear=False",
        "ready volume_l=None",
    ), widgets=widgets)
