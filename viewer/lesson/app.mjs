/**
 * Thin interactive client for the M05 local loopback lesson.
 * ZERO PHYSICS IN JAVASCRIPT: all equations and bounds come verbatim from Python POST /api/*.
 */
import {
  applyControlValue,
  buildSweepBarModel,
  extractPortRows,
  formatIntervalPair,
  verifyOfflineEnvelope,
} from './core.mjs';

const els = {
  presetSelect: document.getElementById('preset-select'),
  presetSummary: document.getElementById('preset-summary'),
  controls: document.getElementById('controls-container'),
  editor: document.getElementById('json-editor'),
  btnSolve: document.getElementById('btn-solve'),
  btnDescribe: document.getElementById('btn-describe'),
  btnSweep: document.getElementById('btn-sweep'),
  badges: document.getElementById('status-badges'),
  alert: document.getElementById('alert-box'),
  provenance: document.getElementById('provenance-line'),
  widths: document.getElementById('widths-line'),
  ports: document.getElementById('ports-container'),
  conservation: document.getElementById('conservation-line'),
  eventsPanel: document.getElementById('events-panel'),
  events: document.getElementById('events-container'),
  sweepPanel: document.getElementById('sweep-panel'),
  sweepChart: document.getElementById('sweep-chart'),
  equations: document.getElementById('equations-pre'),
};

let presets = [];
let activePreset = null;
let currentSystem = null;

function setAlert(kind, text) {
  if (!text) {
    els.alert.className = 'callout hidden';
    els.alert.textContent = '';
    return;
  }
  els.alert.className = `callout ${kind}`;
  els.alert.textContent = text;
}

function setBadges(items) {
  els.badges.replaceChildren();
  for (const [text, cls] of items) {
    const span = document.createElement('span');
    span.className = cls ? `pill ${cls}` : 'pill';
    span.textContent = text;
    els.badges.appendChild(span);
  }
}

async function postJson(route, payload) {
  const res = await fetch(route, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = verifyOfflineEnvelope(await res.json());
  return { status: res.status, data };
}

function readEditorSystem() {
  return JSON.parse(els.editor.value);
}

function renderControls(preset) {
  els.controls.replaceChildren();
  if (!preset.controls || preset.controls.length === 0) {
    const note = document.createElement('p');
    note.className = 'small';
    note.textContent = 'Edit the canonical JSON below to test refusals, unsupported regimes, or custom topologies.';
    els.controls.appendChild(note);
    return;
  }
  for (const ctrl of preset.controls) {
    const lbl = document.createElement('label');
    lbl.setAttribute('for', `ctrl-${ctrl.id}`);
    lbl.textContent = ctrl.label;
    els.controls.appendChild(lbl);

    let curVal = currentSystem;
    for (const seg of ctrl.path) curVal = curVal[seg];

    const row = document.createElement('div');
    row.className = 'ctrl-row';

    const range = document.createElement('input');
    range.type = 'range';
    range.min = String(ctrl.min);
    range.max = String(ctrl.max);
    range.step = String(ctrl.step);
    range.value = String(curVal);

    const text = document.createElement('input');
    text.id = `ctrl-${ctrl.id}`;
    text.type = 'text';
    text.value = String(curVal);

    const sync = (val) => {
      try {
        currentSystem = applyControlValue(readEditorSystem(), ctrl.path, val);
        els.editor.value = JSON.stringify(currentSystem, null, 2);
        range.value = val;
        text.value = val;
      } catch (err) {
        setAlert('err', err.message);
      }
    };
    range.addEventListener('input', () => sync(range.value));
    text.addEventListener('change', () => sync(text.value));

    row.appendChild(range);
    row.appendChild(text);
    els.controls.appendChild(row);
  }
}

function renderPorts(result) {
  const rows = extractPortRows(result);
  if (rows.length === 0) {
    els.ports.textContent = 'No terminal state computed for this outcome.';
    els.conservation.textContent = '';
    return;
  }
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const h of ['Terminal', 'Kind', 'Temperature Bounds', 'Energy / Power', 'Mode / Detail']) {
    const th = document.createElement('th');
    th.textContent = h;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const r of rows) {
    const tr = document.createElement('tr');
    for (const val of [r.name, r.kind, r.temperatureDisplay, r.energyOrPowerDisplay, r.detailDisplay]) {
      const td = document.createElement('td');
      td.textContent = val;
      if (val === r.name || val === r.temperatureDisplay || val === r.energyOrPowerDisplay) {
        td.className = 'mono';
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  els.ports.replaceChildren(table);

  const raw = result.backendResult || {};
  if (raw.energyConservationResidualBoundsJ) {
    els.conservation.textContent =
      `Global energy conservation residual: ${formatIntervalPair(raw.energyConservationResidualBoundsJ, 'J', 6)} (contains 0)`;
  } else if (raw.systemEnergyBalanceBoundsW) {
    els.conservation.textContent =
      `Global steady power balance: ${formatIntervalPair(raw.systemEnergyBalanceBoundsW, 'W', 6)} (contains 0)`;
  } else {
    els.conservation.textContent = '';
  }
}

function renderEvents(result) {
  const raw = result && result.backendResult;
  if (!raw || !Array.isArray(raw.events) || raw.events.length === 0) {
    els.eventsPanel.classList.add('hidden');
    els.events.replaceChildren();
    return;
  }
  els.eventsPanel.classList.remove('hidden');
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  for (const h of ['#', 'Port(s)', 'Transition', 'Certified Event Time', 'Symmetry']) {
    const th = document.createElement('th');
    th.textContent = h;
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const ev of raw.events) {
    const tr = document.createElement('tr');
    const transText = Object.entries(ev.transitions || {})
      .map(([p, t]) => `${p}: ${t.from} -> ${t.to}`)
      .join('; ');
    const cells = [
      String(ev.index + 1),
      (ev.ports || []).join(', '),
      transText,
      formatIntervalPair(ev.timeBoundsS, 's', 5),
      ev.simultaneousSymmetryProven ? 'proven exact tie' : 'sequential',
    ];
    for (const c of cells) {
      const td = document.createElement('td');
      td.textContent = c;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  els.events.replaceChildren(table);
}

function renderSweepChart(points) {
  const bars = buildSweepBarModel(points);
  els.sweepPanel.classList.remove('hidden');
  const svgNS = 'http://www.w3.org/2000/svg';
  els.sweepChart.replaceChildren();

  const leftPad = 76;
  const maxBarW = 330;
  const rowH = 36;

  bars.forEach((b, idx) => {
    const y = 18 + idx * rowH;

    const rLbl = document.createElementNS(svgNS, 'text');
    rLbl.setAttribute('x', '10');
    rLbl.setAttribute('y', String(y + 18));
    rLbl.setAttribute('font-size', '12');
    rLbl.setAttribute('fill', '#16343b');
    rLbl.textContent = `r = ${b.radiusM} m`;
    els.sweepChart.appendChild(rLbl);

    const rect = document.createElementNS(svgNS, 'rect');
    rect.setAttribute('x', String(leftPad));
    rect.setAttribute('y', String(y + 4));
    rect.setAttribute('width', String(Math.max(4, Math.round(b.barFraction * maxBarW))));
    rect.setAttribute('height', '20');
    rect.setAttribute('rx', '4');
    rect.setAttribute('fill', '#1f767d');
    els.sweepChart.appendChild(rect);

    const vLbl = document.createElementNS(svgNS, 'text');
    vLbl.setAttribute('x', String(leftPad + Math.max(4, Math.round(b.barFraction * maxBarW)) + 8));
    vLbl.setAttribute('y', String(y + 18));
    vLbl.setAttribute('font-size', '11');
    vLbl.setAttribute('fill', '#2b4f56');
    vLbl.textContent = b.label;
    els.sweepChart.appendChild(vLbl);
  });
}

async function runDescribe() {
  setAlert('', '');
  els.sweepPanel.classList.add('hidden');
  let payload;
  try {
    payload = readEditorSystem();
  } catch (err) {
    setAlert('err', `Invalid JSON: ${err.message}`);
    return;
  }
  const { status, data } = await postJson('/api/describe', payload);
  if (status !== 200 || !data.ok) {
    setBadges([['Refused (HTTP ' + status + ')', 'err']]);
    setAlert('err', data.error || 'Equation derivation refused by Python backend.');
    return;
  }
  const eq = data.equations;
  els.equations.textContent = eq.equationsText || '';
  const badges = [[`Mode: ${eq.mode}`, '']];
  if (eq.unsupportedRegime) {
    badges.push(['unsupported_regime', 'warn']);
    setAlert('warn', `${eq.unsupportedRegime.pair.join(' + ')}: ${eq.unsupportedRegime.reason}`);
  } else {
    badges.push([`Backend: ${eq.selectedBackend}`, '']);
  }
  setBadges(badges);
  els.provenance.textContent =
    `nativeExecuted=${data.nativeExecuted} · nativeQualified=${data.nativeQualified} · derivedLawSha256=${eq.derivedLawSha256.slice(0, 16)}…`;
}

async function runSolve() {
  setAlert('', '');
  els.btnSolve.disabled = true;
  let payload;
  try {
    payload = readEditorSystem();
  } catch (err) {
    els.btnSolve.disabled = false;
    setAlert('err', `Invalid JSON: ${err.message}`);
    return;
  }
  try {
    const { status, data } = await postJson('/api/solve', payload);
    if (status !== 200 || !data.ok) {
      setBadges([['Refused (HTTP ' + status + ')', 'err']]);
      setAlert('err', data.error || 'Solve refused by Python backend.');
      els.ports.textContent = 'No result returned due to refusal.';
      els.eventsPanel.classList.add('hidden');
      return;
    }
    const r = data.result;
    if (r.equations && r.equations.equationsText) {
      els.equations.textContent = r.equations.equationsText;
    }
    const statusCls =
      r.status === 'unsupported_regime' || r.status === 'mode_sequence_uncertain' ? 'warn' : '';
    setBadges([
      [`Status: ${r.status}`, statusCls],
      [`Termination: ${r.terminationReason}`, statusCls],
      [`Backend: ${r.backend || 'none'}`, ''],
    ]);
    if (r.status === 'unsupported_regime') {
      setAlert('warn', `Unsupported regime [${(r.unsupportedMechanismPair || []).join(', ')}]: ${r.reason}`);
    } else if (r.status === 'mode_sequence_uncertain') {
      const sr = r.backendResult?.solverMetadata?.stopReason || 'unresolved transition ordering';
      setAlert('warn', `Certified mode_sequence_uncertain (${sr}). Physical state up to modeled stop remains enclosed.`);
    }
    els.provenance.textContent =
      `nativeExecuted=${r.nativeExecuted} · nativeQualified=${r.nativeQualified} · independentlyCertifiedReference=${r.independentlyCertifiedReference} · runnerConsumable=${r.runnerConsumable}`;
    els.widths.textContent =
      'Achieved widths: ' +
      Object.entries(r.achievedWidths || {})
        .map(([k, v]) => `${k}=${v}`)
        .join(' · ');
    renderPorts(r);
    renderEvents(r);
  } finally {
    els.btnSolve.disabled = false;
  }
}

async function runCriticalRadiusSweep() {
  if (!activePreset || !activePreset.sweepSpec) return;
  setAlert('', '');
  els.btnSweep.disabled = true;
  try {
    const baseSys = readEditorSystem();
    const spec = activePreset.sweepSpec;
    const points = [];
    for (const rVal of spec.values) {
      const candidate = applyControlValue(baseSys, spec.path, rVal);
      const { status, data } = await postJson('/api/solve', candidate);
      if (status !== 200 || !data.ok) {
        setAlert('err', `Sweep at r=${rVal} m refused: ${data.error}`);
        return;
      }
      const portData = data.result.backendResult.ports[spec.metricPort];
      points.push({ radiusM: rVal, heatLossBoundsW: portData.outwardHeatRateBoundsW });
    }
    renderSweepChart(points);
  } finally {
    els.btnSweep.disabled = false;
  }
}

function selectPreset(key) {
  activePreset = presets.find((p) => p.key === key) || presets[0];
  currentSystem = structuredClone(activePreset.system);
  els.presetSummary.textContent = activePreset.summary;
  els.editor.value = JSON.stringify(currentSystem, null, 2);
  renderControls(activePreset);
  els.sweepPanel.classList.add('hidden');
  if (activePreset.sweepSpec) {
    els.btnSweep.classList.remove('hidden');
    els.btnSweep.disabled = false;
  } else {
    els.btnSweep.classList.add('hidden');
  }
  runSolve();
}

async function init() {
  const res = await fetch('/api/presets');
  const data = verifyOfflineEnvelope(await res.json());
  presets = data.presets || [];
  els.presetSelect.replaceChildren();
  for (const p of presets) {
    const opt = document.createElement('option');
    opt.value = p.key;
    opt.textContent = p.title;
    els.presetSelect.appendChild(opt);
  }
  els.presetSelect.disabled = false;
  els.btnSolve.disabled = false;
  els.btnDescribe.disabled = false;

  els.presetSelect.addEventListener('change', () => selectPreset(els.presetSelect.value));
  els.btnSolve.addEventListener('click', () => runSolve());
  els.btnDescribe.addEventListener('click', () => runDescribe());
  els.btnSweep.addEventListener('click', () => runCriticalRadiusSweep());

  if (presets.length > 0) {
    selectPreset(presets[0].key);
  }
}

init().catch((err) => {
  setBadges([['Initialization error', 'err']]);
  setAlert('err', String(err));
});
