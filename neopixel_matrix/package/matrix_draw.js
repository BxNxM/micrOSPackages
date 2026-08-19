const matrixContainer = document.getElementById('matrix');
const colorPicker = document.getElementById('colorPicker');
const sizeInput = document.getElementById('matrixSize');
let pixels = [];
let drawing = false;
let activePointerId = null;
const supportsPointer = window.PointerEvent;

let lastX = null;
let lastY = null;

let updateQueue = [];
let updating = false;

async function processQueue() {
  if (updating || updateQueue.length === 0) return;
  updating = true;
  const { cmd } = updateQueue.shift();
  try {
    await restAPI(cmd, true);
  } catch (err) {
    console.warn("REST call failed:", err);
  }
  updating = false;
  if (updateQueue.length > 0) processQueue();
}

function queueUpdate(cmd) {
  updateQueue.push({ cmd });
  processQueue();
}

function startDrawing(e) {
  drawing = true;
  if (supportsPointer) {
    activePointerId = e.pointerId;
    matrixContainer.setPointerCapture(activePointerId);
  }
  paintPixel(e.target);
  e.preventDefault();
}

function moveDrawing(e) {
  if (!drawing) return;
  let target;
  if (supportsPointer) {
    target = document.elementFromPoint(e.clientX, e.clientY);
  } else if (e.touches && e.touches.length) {
    const t = e.touches[0];
    target = document.elementFromPoint(t.clientX, t.clientY);
    e.preventDefault();
  } else {
    target = document.elementFromPoint(e.clientX, e.clientY);
  }
  if (target && target.classList.contains('pixel')) {
    paintPixel(target);
  }
}

function stopDrawing() {
  drawing = false;
  lastX = null;
  lastY = null;
  if (supportsPointer && activePointerId !== null) {
    matrixContainer.releasePointerCapture(activePointerId);
    activePointerId = null;
  }
}

function hexToRgb(hex) {
  const val = parseInt(hex.slice(1), 16);
  return [(val >> 16) & 255, (val >> 8) & 255, val & 255];
}

function buildMatrix(size) {
  matrixContainer.innerHTML = "";
  pixels = [];
  matrixContainer.style.gridTemplateColumns = `repeat(${size}, 30px)`;
  matrixContainer.style.gridTemplateRows = `repeat(${size}, 30px)`;

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const cell = document.createElement('div');
      cell.className = "pixel";
      cell.dataset.x = x;
      cell.dataset.y = y;
      cell.dataset.color = "#000000";
      cell.style.backgroundColor = "#000000";
      if (supportsPointer) {
        cell.addEventListener('pointerdown', startDrawing);
      } else {
        cell.addEventListener('mousedown', startDrawing);
        cell.addEventListener('touchstart', startDrawing, { passive: false });
      }
      matrixContainer.appendChild(cell);
      pixels.push(cell);
    }
  }
  sendClearCommand();
}

function paintPixel(pixelDiv) {
  const color = colorPicker.value;
  const x = parseInt(pixelDiv.dataset.x);
  const y = parseInt(pixelDiv.dataset.y);

  if (x === lastX && y === lastY) return;
  lastX = x;
  lastY = y;

  pixelDiv.dataset.color = color;
  pixelDiv.style.backgroundColor = color;

  const [r, g, b] = hexToRgb(color);
  const cmd = `neomatrix/draw_colormap/[(${x},${y},(${r},${g},${b}))]`;
  queueUpdate(cmd);
}

function clearMatrix() {
  pixels.forEach(p => {
    p.dataset.color = "#000000";
    p.style.backgroundColor = "#000000";
  });
  sendClearCommand();
}

function sendClearCommand() {
  queueUpdate("neomatrix/draw_colormap/[]");
}

function applySize() {
  buildMatrix(parseInt(sizeInput.value, 10));
}

function parseTuplesRegex(str) {
  if (!str || typeof str !== 'string') return null;
  const out = [];
  const re = /\(\s*(\d+)\s*,\s*(\d+)\s*,\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*\)/g;
  let m;
  while ((m = re.exec(str)) !== null) {
    out.push({ x:+m[1], y:+m[2], r:+m[3], g:+m[4], b:+m[5] });
  }
  return out.length ? out : null;
}

function rgbToHex(r, g, b) {
  const toHex = (n) => Math.max(0, Math.min(255, n|0)).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function blackoutMatrixUI() {
  const cells = document.querySelectorAll('.pixel');
  cells.forEach(p => { p.dataset.color = "#000000"; p.style.backgroundColor = "#000000"; });
}

function ensureGridFits(cells) {
  if (!Array.isArray(cells) || !cells.length) return;
  const maxX = Math.max(...cells.map(c => c.x));
  const maxY = Math.max(...cells.map(c => c.y));
  const need = Math.max(maxX, maxY) + 1;
  const current = parseInt(document.getElementById('matrixSize').value, 10) || 8;
  if (need > current) {
    document.getElementById('matrixSize').value = need;
    applySize();
  }
}

async function getMatrixState() {
  const btn = document.getElementById('readStateBtn');
  const out = document.getElementById('matrixStateOut');
  if (btn) btn.disabled = true;
  if (out) out.value = "Reading…";

  try {
    const resp = await restAPI('neomatrix/get_colormap', true);

    let raw = '';
    if (resp && typeof resp === 'object' && 'result' in resp) raw = String(resp.result);
    else if (typeof resp === 'string') raw = resp;
    else if (resp && typeof resp.text === 'string') raw = resp.text;
    else if (resp && typeof resp.body === 'string') raw = resp.body;
    else raw = JSON.stringify(resp);

    const oneLine = String(raw).replace(/[\r\n]+/g, ' ').trim();
    if (out) out.value = oneLine;

    const parsed = parseTuplesRegex(oneLine);
    blackoutMatrixUI();
    if (!parsed) return;

    ensureGridFits(parsed);

    for (const {x,y,r,g,b} of parsed) {
      const cell = document.querySelector(`.pixel[data-x="${x}"][data-y="${y}"]`);
      if (!cell) continue;
      const hex = rgbToHex(r,g,b);
      cell.dataset.color = hex;
      cell.style.backgroundColor = hex;
    }
  } catch (e) {
    if (out) out.value = "Error: could not read matrix state.";
    blackoutMatrixUI();
  } finally {
    if (btn) btn.disabled = false;
  }
}

function setSenderStatus(msg, isError=false){
  const el = document.getElementById('matrixInputStatus');
  if (!el) return;
  el.textContent = msg;
  el.style.color = isError ? '#f99' : '#9cf';
}

function applyCellsToUI(cells){
  for (const {x,y,r,g,b} of cells) {
    const cell = document.querySelector(`.pixel[data-x="${x}"][data-y="${y}"]`);
    if (!cell) continue;
    const toHex = n => Math.max(0,Math.min(255,n|0)).toString(16).padStart(2,'0');
    const hex = `#${toHex(r)}${toHex(g)}${toHex(b)}`;
    cell.dataset.color = hex;
    cell.style.backgroundColor = hex;
  }
}

function buildPayload(cells){
  const parts = cells.map(({x,y,r,g,b}) => `(${x},${y},(${r},${g},${b}))`);
  return `[${parts.join(',')}]`.replace(/\//g, '');
}

function getMatrixCellsFromUI(){
  const cells = [];
  document.querySelectorAll('.pixel').forEach(cell => {
    const x = parseInt(cell.dataset.x, 10);
    const y = parseInt(cell.dataset.y, 10);
    const [r, g, b] = hexToRgb(cell.dataset.color || '#000000');
    cells.push({x, y, r, g, b});
  });
  return cells;
}

function buildJsonFrame(cells){
  return JSON.stringify(cells.map(({x,y,r,g,b}) => [x, y, [r, g, b]]));
}

function buildJsonLines(raw){
  const lines = String(raw || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const sourceLines = lines.length ? lines : [String(raw || '').trim()];
  const frames = [];
  let cells = 0;
  for (const line of sourceLines) {
    const parsed = parseTuplesRegex(line);
    if (!parsed) return null;
    frames.push(buildJsonFrame(parsed));
    cells += parsed.length;
  }
  return { text: frames.join('\n') + '\n', frames: frames.length, cells };
}

function appendMatrixFrameLine(frameText){
  const input = document.getElementById('matrixInput');
  if (!input) return;
  const normalized = frameText.trim();
  if (!normalized) return;
  const lines = input.value.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (lines[lines.length - 1] === normalized) {
    setSenderStatus('Frame unchanged. Not added again.');
    return;
  }
  const existing = input.value.trim();
  input.value = existing ? `${existing}\n${normalized}` : normalized;
  setSenderStatus(`Added frame ${lines.length + 1}.`);
}

async function copyTextToClipboard(text){
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}

function applyMatrixInputLocally(){
  const raw = (document.getElementById('matrixInput')?.value || '').trim();
  const parsed = parseTuplesRegex(raw);
  if (!parsed) { setSenderStatus('Could not parse input. Use [(x,y,(r,g,b)), ...]', true); return; }
  applyCellsToUI(parsed);
  setSenderStatus(`Applied ${parsed.length} cells locally.`);
}

function addReadStateFrame(){
  const raw = (document.getElementById('matrixStateOut')?.value || '').trim();
  const uiFrame = getMatrixCellsFromUI();
  const parsed = uiFrame.length ? uiFrame : parseTuplesRegex(raw);
  if (!parsed || !parsed.length) { setSenderStatus('Could not add frame.', true); return; }
  appendMatrixFrameLine(buildPayload(parsed));
}

function sendMatrixFromInput(){
  const btn = document.getElementById('sendMatrixBtn');
  const raw = (document.getElementById('matrixInput')?.value || '').trim();
  const parsed = parseTuplesRegex(raw);
  if (!parsed) { setSenderStatus('Could not parse input. Use [(x,y,(r,g,b)), ...]', true); return; }

  if (btn) btn.disabled = true;
  setSenderStatus(`Sending current input as REST batches (${parsed.length} cells)…`);

  applyCellsToUI(parsed);

  const CHUNK = 10;
  let sent = 0;
  for (let i = 0; i < parsed.length; i += CHUNK) {
    const chunk = parsed.slice(i, i + CHUNK);
    const payload = buildPayload(chunk);
    const cmd = `neomatrix/draw_colormap/${payload}`;
    queueUpdate(cmd);
    sent += chunk.length;
  }

  setSenderStatus(`Queued ${sent} cells in ${Math.ceil(parsed.length / CHUNK)} batch(es).`);
  if (btn) btn.disabled = false;
}

async function copyMatrixInputJson(){
  const raw = (document.getElementById('matrixInput')?.value || '').trim();
  const exported = buildJsonLines(raw);
  if (!exported) { setSenderStatus('Could not export. Use one tuple-list frame per line.', true); return; }
  const out = document.getElementById('matrixJsonOut');
  let json = exported.text;
  if (out) {
    const existing = out.value.trim();
    out.value = existing ? `${existing}\n${json}` : json;
    json = out.value.endsWith('\n') ? out.value : `${out.value}\n`;
    out.select();
  }
  try {
    await copyTextToClipboard(json);
    setSenderStatus(`Exported ${exported.frames} JSONL frame(s), ${exported.cells} cells total. Copied.`);
  } catch (e) {
    setSenderStatus('Clipboard blocked. JSONL frames are shown and selected.', true);
  }
}

function wireControls() {
  document.getElementById('resizeBtn')?.addEventListener('click', applySize);
  document.getElementById('clearBtn')?.addEventListener('click', clearMatrix);
  document.getElementById('stopAnimationBtn')?.addEventListener('click', () => restAPI('neomatrix/stop', true));
  document.getElementById('startAnimationBtn')?.addEventListener('click', () => restAPI('neomatrix/snake', true));
  document.getElementById('readStateBtn')?.addEventListener('click', getMatrixState);
  document.getElementById('addFrameBtn')?.addEventListener('click', addReadStateFrame);
  document.getElementById('sendMatrixBtn')?.addEventListener('click', sendMatrixFromInput);
  document.getElementById('applyMatrixBtn')?.addEventListener('click', applyMatrixInputLocally);
  document.getElementById('exportJsonBtn')?.addEventListener('click', copyMatrixInputJson);
}

function wireDrawing() {
  if (supportsPointer) {
    matrixContainer.addEventListener('pointermove', moveDrawing);
    window.addEventListener('pointerup', stopDrawing);
    window.addEventListener('pointercancel', stopDrawing);
    matrixContainer.addEventListener('pointerleave', stopDrawing);
  } else {
    matrixContainer.addEventListener('mousemove', moveDrawing);
    matrixContainer.addEventListener('touchmove', moveDrawing, { passive: false });
    window.addEventListener('mouseup', stopDrawing);
    window.addEventListener('touchend', stopDrawing);
    window.addEventListener('touchcancel', stopDrawing);
    matrixContainer.addEventListener('mouseleave', stopDrawing);
  }
}

function initMatrixDraw() {
  wireControls();
  wireDrawing();
  buildMatrix(parseInt(sizeInput.value, 10));
  restInfo(false);
}

window.applySize = applySize;
window.clearMatrix = clearMatrix;
window.getMatrixState = getMatrixState;
window.applyMatrixInputLocally = applyMatrixInputLocally;
window.addReadStateFrame = addReadStateFrame;
window.sendMatrixFromInput = sendMatrixFromInput;
window.copyMatrixInputJson = copyMatrixInputJson;

initMatrixDraw();
