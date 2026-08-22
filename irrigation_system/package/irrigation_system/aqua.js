const state = {
  data: null,
  statusAt: 0,
  busy: false,
  runSource: "total",
  configDirty: false,
};

const configFields = {
  tankWidthInput: "tank_width_cm",
  tankDepthInput: "tank_depth_cm",
  tankHeightInput: "tank_height_cm",
  waterDistanceInput: "water_distance_cm",
  minLevelInput: "min_level_percent",
  pumpFlowInput: "pump_l_hour",
  headCountInput: "head_count",
  soilSensorCountInput: "soil_sensor_count",
  levelModuleInput: "level_module",
  pumpPinInput: "pump_pin",
};

function apiPath() {
  return "/aqua/api";
}

function byId(id) {
  return document.getElementById(id);
}

function numberValue(id) {
  const value = byId(id)?.value;
  if (value === "" || value === null || typeof value === "undefined") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function textValue(id) {
  const value = byId(id)?.value;
  return value && value.trim() ? value.trim() : null;
}

function setText(id, value) {
  const el = byId(id);
  if (el) el.textContent = value;
}

function setMessage(message, type = "neutral") {
  const el = byId("messageLine");
  if (!el) return;
  el.textContent = message;
  el.dataset.type = type;
}

function trimDecimalZeros(value) {
  return value.includes(".") ? value.replace(/0+$/, "").replace(/\.$/, "") : value;
}

function fmt(value, suffix = "", digits = 1) {
  if (value === null || typeof value === "undefined" || Number.isNaN(Number(value))) {
    return "--" + suffix;
  }
  const n = Number(value);
  const fixed = Number.isInteger(n) ? String(n) : n.toFixed(digits);
  return trimDecimalZeros(fixed) + suffix;
}

function clampCount(value, minimum = 0) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return minimum;
  return Math.max(minimum, Math.min(100, Math.trunc(parsed)));
}

function inputText(value, digits = 3) {
  if (value === null || typeof value === "undefined" || Number.isNaN(Number(value))) return "";
  const fixed = Number(value).toFixed(digits);
  return trimDecimalZeros(fixed);
}

function setNumberInput(id, value, digits = 3) {
  const el = byId(id);
  if (!el || document.activeElement === el) return;
  el.value = inputText(value, digits);
}

function markConfigDirty() {
  state.configDirty = true;
  setText("saveState", "not saved");
}

function isManualLevelModule(value) {
  return levelModuleKey(value) === "manual";
}

function levelModuleKey(value) {
  const key = String(value || "manual").toLowerCase();
  if (["manual", "none", "no_sensor", "no-sensor", "nosensor", "disabled", "disable", "off", "false", "0"].includes(key)) {
    return "manual";
  }
  if (key.includes("hcsr04") || key.includes("hc-sr04")) return "hcsr04";
  if (key.includes("rcwl")) return "rcwl1670";
  return key;
}

function selectedLevelModule(config = null) {
  const select = byId("levelModuleInput");
  if (state.configDirty && select) return select.value;
  return select?.value || config?.level_module || "manual";
}

function updateManualDistanceVisibility(config = null) {
  const module = selectedLevelModule(config);
  const manual = isManualLevelModule(module);
  const field = byId("waterDistanceField");
  const input = byId("waterDistanceInput");
  const sensorField = byId("sensorDistanceField");
  if (field) field.hidden = !manual;
  if (input) input.disabled = !manual;
  if (sensorField) sensorField.hidden = manual;
  renderSensorDistanceReadout(state.data, module);
}

async function requestStatus() {
  const response = await fetch(apiPath(), { cache: "no-store" });
  if (!response.ok) throw new Error("status " + response.status);
  return response.json();
}

async function postAction(action, payload = {}) {
  const response = await fetch(apiPath(), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ action, ...payload }),
  });
  if (!response.ok) throw new Error("status " + response.status);
  return response.json();
}

function badge(id, text, kind) {
  const el = byId(id);
  if (!el) return;
  el.textContent = text;
  el.className = "badge" + (kind ? " " + kind : "");
}

function renderBadges(data) {
  const ready = data.ready || {};
  const tank = data.tank || {};
  const pumpOn = Boolean(data.pump_on);

  if (ready.ok) {
    badge("readyBadge", "Ready", "ok");
  } else {
    badge("readyBadge", "Locked", "alert");
  }

  badge("pumpBadge", pumpOn ? "Pump on" : "Pump off", pumpOn ? "warn" : "");

  const level = tank.level_percent;
  if (level === null || typeof level === "undefined") {
    badge("levelBadge", "Level unknown", "warn");
  } else if (level < (data.config?.min_level_percent || 0)) {
    badge("levelBadge", "Tank low", "alert");
  } else {
    badge("levelBadge", fmt(level, "%"), "ok");
  }
}

function renderHeads(count, headFlow) {
  const grid = byId("headGrid");
  if (!grid) return;
  grid.innerHTML = "";
  const safeCount = clampCount(count, 1);
  for (let i = 0; i < safeCount; i += 1) {
    const head = document.createElement("div");
    head.className = "head";
    head.innerHTML = `
      <div class="drops" aria-hidden="true"><span></span><span></span><span></span></div>
      <strong>Head ${i + 1}</strong>
      <span>${fmt(headFlow, " L/h")}</span>
    `;
    grid.appendChild(head);
  }
}

function soilLevelClass(value) {
  const moisture = Number(value);
  if (!Number.isFinite(moisture)) return "";
  if (moisture < 35) return "dry";
  if (moisture > 72) return "wet";
  return "ok";
}

function renderSoilSensors(soil) {
  const grid = byId("soilGrid");
  if (!grid) return;
  const sensors = Array.isArray(soil?.sensors) ? soil.sensors.slice(0, 100) : [];
  const count = clampCount(soil?.count ?? sensors.length, 0);
  const average = soil?.average_percent;

  setText("soilSummary", count ? `${count} sensors / avg ${fmt(average, "%")}` : "0 sensors");
  grid.innerHTML = "";

  if (!count) {
    const empty = document.createElement("div");
    empty.className = "soil-empty";
    empty.textContent = "No soil sensors";
    grid.appendChild(empty);
    return;
  }

  sensors.forEach((sensor, index) => {
    const moisture = sensor.moisture_percent;
    const tile = document.createElement("div");
    tile.className = `soil-sensor ${soilLevelClass(moisture)}`;
    tile.innerHTML = `
      <span class="soil-probe" aria-hidden="true"></span>
      <strong>S${sensor.id || index + 1}</strong>
      <span>${fmt(moisture, "%")}</span>
    `;
    grid.appendChild(tile);
  });
}

function levelModuleLabel(value) {
  const key = levelModuleKey(value);
  if (key === "hcsr04") return "HC-SR04";
  if (key === "rcwl1670") return "RCWL-1670";
  if (key === "manual") return "No sensor";
  return value ? String(value) : "--";
}

function renderSensorDistanceReadout(data, module = null) {
  const el = byId("sensorDistanceReadout");
  if (!el) return;

  const activeModule = module || data?.config?.level_module;
  if (isManualLevelModule(activeModule)) {
    el.value = "";
    return;
  }

  const sensor = data?.level_sensor || {};
  const activeKey = levelModuleKey(activeModule);
  const sensorKey = levelModuleKey(sensor.module);
  if (sensor.state && activeKey === sensorKey && Number.isFinite(Number(sensor.distance_cm))) {
    el.value = fmt(sensor.distance_cm, " cm");
  } else if (sensor.error && activeKey === sensorKey) {
    el.value = "offline";
  } else {
    el.value = "-- cm";
  }
}

function renderLevelSensor(data) {
  const sensor = data.level_sensor || {};
  const moduleName = sensor.module || data.config?.level_module;
  const label = levelModuleLabel(moduleName);

  if (String(sensor.source || "").startsWith("manual") && Number.isFinite(Number(sensor.distance_cm))) {
    setText("metricSensor", `Manual ${fmt(sensor.distance_cm, " cm")}`);
  } else if (label === "No sensor" || sensor.enabled === false) {
    setText("metricSensor", "No sensor");
  } else if (sensor.state && Number.isFinite(Number(sensor.distance_cm))) {
    setText("metricSensor", `${label} ${fmt(sensor.distance_cm, " cm")}`);
  } else if (sensor.error) {
    setText("metricSensor", `${label} offline`);
  } else {
    setText("metricSensor", label);
  }
  renderSensorDistanceReadout(data);
}

function fillInputs(config) {
  if (state.configDirty) return;
  Object.keys(configFields).forEach((id) => {
    const el = byId(id);
    const key = configFields[id];
    if (!el || document.activeElement === el) return;
    const value = config?.[key];
    if (id === "levelModuleInput") {
      el.value = levelModuleKey(value);
      return;
    }
    el.value = value === null || typeof value === "undefined" ? "" : value;
  });
}

function runEstimate() {
  const data = state.data || {};
  const config = data.config || {};
  const heads = clampCount(config.head_count || 1, 1);
  const pump = Number(config.pump_l_hour || 0);
  let totalVolume = numberValue("runVolume") || 0;
  let perHead = numberValue("runPerHead") || 0;

  if (state.runSource === "perHead") {
    totalVolume = perHead * heads;
    setNumberInput("runVolume", totalVolume);
  } else {
    perHead = heads > 0 ? totalVolume / heads : 0;
    setNumberInput("runPerHead", perHead);
  }

  return {
    heads,
    pump,
    totalVolume,
    perHead,
    duration: pump > 0 ? totalVolume * 3600 / pump : 0,
  };
}

function wateringRun(data = state.data) {
  return data?.runtime?.watering || null;
}

function projectedRun(run) {
  if (!run) return null;
  const duration = Number(run.duration_s) || 0;
  const target = Number(run.target_l) || 0;
  const baseRemaining = Number(run.remaining_s);
  const baseDispensed = Number(run.dispensed_l);
  const age = run.active && state.statusAt ? Math.max(0, (Date.now() - state.statusAt) / 1000) : 0;
  const remaining = Math.max(0, (Number.isFinite(baseRemaining) ? baseRemaining : duration) - age);
  const elapsed = Math.max(0, duration - remaining);
  const ratio = duration > 0 ? Math.min(1, elapsed / duration) : (remaining <= 0 ? 1 : 0);
  const dispensed = duration > 0 ? target * ratio : Math.max(0, baseDispensed || 0);
  return {
    active: Boolean(run.active && remaining > 0),
    remaining_s: remaining,
    dispensed_l: Math.min(target, dispensed),
    target_l: target,
  };
}

function renderLiveRun(data = state.data) {
  const flow = data?.flow || {};
  const run = projectedRun(wateringRun(data));
  const active = Boolean(run?.active || (data?.pump_on && !run));
  const availableAfterCard = byId("availableAfterCard");

  setText("pumpState", active ? "Watering" : "Idle");
  setText("pumpFlow", active && run ? `${fmt(run.dispensed_l, " L", 2)} / ${fmt(run.target_l, " L", 2)}` : fmt(flow.pump_l_hour, " L/h"));
  document.querySelector(".pump-node")?.classList.toggle("is-watering", active);
  const waterBtn = byId("waterBtn");
  if (waterBtn) waterBtn.disabled = Boolean(active || state.busy);

  if (active && run) {
    setText("previewDurationLabel", "Countdown");
    setText("previewDuration", fmt(run.remaining_s, " s"));
    setText("previewWaterLabel", "Outgoing");
    setText("previewAvailableAfter", `${fmt(run.dispensed_l, " L", 3)} / ${fmt(run.target_l, " L", 3)}`);
    availableAfterCard?.classList.remove("is-alert");
  } else {
    const estimate = runEstimate();
    const tank = state.data?.tank || {};
    const usable = Number(tank.usable_l);
    const rawAfter = Number.isFinite(usable) ? usable - estimate.totalVolume : null;
    const after = rawAfter === null ? null : Math.max(0, rawAfter);
    setText("previewDurationLabel", "Pump runtime");
    setText("previewDuration", fmt(estimate.duration, " s"));
    setText("previewWaterLabel", "Available after");
    setText("previewAvailableAfter", fmt(after, " L", 3));
    availableAfterCard?.classList.toggle("is-alert", rawAfter !== null && rawAfter < 0);
  }
}

function renderStatus(data) {
  state.data = data;
  state.statusAt = Date.now();
  const tank = data.tank || {};
  const flow = data.flow || {};
  const soil = data.soil || {};
  const config = data.config || {};
  const headCount = flow.head_count || config.head_count || 0;
  const soilCount = soil.count ?? config.soil_sensor_count ?? 0;

  const level = Number(tank.level_percent);
  const minLevel = Number(config.min_level_percent);
  const fill = byId("tankFill");
  if (fill) fill.style.height = Number.isFinite(level) ? `${Math.max(0, Math.min(100, level))}%` : "0%";
  const marker = byId("minLevelMarker");
  if (marker) {
    marker.hidden = !Number.isFinite(minLevel);
    marker.style.bottom = `${Math.max(0, Math.min(100, minLevel || 0))}%`;
  }

  setText("tankPercent", Number.isFinite(level) ? fmt(level, "%") : "--%");
  setText("tankVolume", fmt(tank.volume_l, " L"));
  setText("tankCapacity", fmt(tank.capacity_l, " L"));
  setText("minLevelLabel", Number.isFinite(minLevel) ? `Min ${fmt(minLevel, "%")}` : "Min --%");
  setText("schemeSummary", `${headCount} heads / ${soilCount} sensors`);
  setText("usableWater", fmt(tank.usable_l, " L"));
  setText("metricPump", fmt(flow.pump_l_hour, " L/h"));
  setText("metricHead", fmt(flow.head_l_hour, " L/h"));
  setText("metricReserve", fmt(tank.reserve_l, " L"));

  renderHeads(headCount || 1, flow.head_l_hour || 0);
  renderSoilSensors(soil);
  renderLevelSensor(data);
  renderBadges(data);
  fillInputs(config);
  updateManualDistanceVisibility(config);
  renderLiveRun(data);
}

async function refresh() {
  if (state.busy) return;
  try {
    const data = await requestStatus();
    renderStatus(data);
    setMessage("Synced");
  } catch (err) {
    setMessage("Aqua API unavailable. Run `aqua load` on the device.", "error");
    badge("readyBadge", "Offline", "alert");
  }
}

function configPayload() {
  const payload = {};
  Object.keys(configFields).forEach((id) => {
    const key = configFields[id];
    payload[key] = byId(id)?.type === "number" ? numberValue(id) : textValue(id);
  });
  if (!isManualLevelModule(payload.level_module)) {
    delete payload.water_distance_cm;
  }
  return payload;
}

async function saveConfig(event) {
  event.preventDefault();
  state.busy = true;
  byId("saveConfigBtn").disabled = true;
  setText("saveState", "saving");
  try {
    const data = await postAction("configure", { config: configPayload() });
    state.configDirty = false;
    renderStatus(data);
    setText("saveState", "saved");
    setMessage("Configuration saved");
  } catch (err) {
    setText("saveState", "not saved");
    setMessage("Save failed", "error");
  } finally {
    byId("saveConfigBtn").disabled = false;
    state.busy = false;
  }
}

async function startWatering() {
  const run = {};
  const estimate = runEstimate();
  if (estimate.totalVolume && estimate.totalVolume > 0) {
    run.volume_l = estimate.totalVolume;
  } else {
    setMessage("Enter a water amount", "error");
    return;
  }

  byId("waterBtn").disabled = true;
  state.busy = true;
  try {
    const data = await postAction("water", { run });
    if (data.state === false) {
      setMessage(data.error || "Watering blocked", "error");
    } else {
      setMessage("Watering started");
    }
    state.busy = false;
    await refresh();
  } catch (err) {
    setMessage("Watering command failed", "error");
  } finally {
    state.busy = false;
    byId("waterBtn").disabled = Boolean(projectedRun(wateringRun())?.active);
  }
}

async function stopWatering() {
  byId("stopBtn").disabled = true;
  state.busy = true;
  try {
    await postAction("stop");
    setMessage("Pump stopped");
    state.busy = false;
    await refresh();
  } catch (err) {
    setMessage("Stop failed", "error");
  } finally {
    state.busy = false;
    byId("stopBtn").disabled = false;
  }
}

function wire() {
  byId("refreshBtn")?.addEventListener("click", refresh);
  byId("configForm")?.addEventListener("submit", saveConfig);
  byId("waterBtn")?.addEventListener("click", startWatering);
  byId("stopBtn")?.addEventListener("click", stopWatering);
  byId("runVolume")?.addEventListener("input", () => {
    state.runSource = "total";
    renderLiveRun();
  });
  byId("runPerHead")?.addEventListener("input", () => {
    state.runSource = "perHead";
    renderLiveRun();
  });
  Object.keys(configFields).forEach((id) => {
    byId(id)?.addEventListener("input", () => {
      markConfigDirty();
      if (id === "levelModuleInput") updateManualDistanceVisibility();
    });
  });
  byId("levelModuleInput")?.addEventListener("change", () => {
    markConfigDirty();
    updateManualDistanceVisibility();
  });
}

wire();
updateManualDistanceVisibility();
refresh();
setInterval(refresh, 5000);
setInterval(renderLiveRun, 1000);
