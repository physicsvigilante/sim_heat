/**
 * Pure presentation & validation helpers for the M05 interactive lesson UI.
 *
 * ARCHITECTURAL INVARIANT: ZERO PHYSICS IN JAVASCRIPT.
 * This module never solves ODEs, never computes conductances/exponentials/temperatures/
 * critical radii, and never alters physical bounds. It only:
 *   1. Clones and updates parameter strings inside canonical sim_heat.thermal_system/1 JSON;
 *   2. Validates honest offline provenance flags on Python loopback responses;
 *   3. Formats exact rational strings ("p/q") into fixed-decimal previews for display
 *      (pure exact BigInt string division);
 *   4. Extracts display rows and SVG bar geometry strictly from Python-returned bounds.
 */

const OFFLINE_FLAGS = [
  'nativeExecuted',
  'nativeQualified',
  'independentlyCertifiedReference',
  'runnerConsumable',
];

const DECIMAL_RE = /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/;
const RATIONAL_RE = /^(-?[0-9]+)(?:\/([1-9][0-9]*))?$/;

/** Validate an unsigned SI decimal string before sending to Python. */
export function normalizeDecimalInput(raw) {
  const s = String(raw).trim();
  if (!DECIMAL_RE.test(s)) {
    throw new Error(`Expected unsigned SI decimal string, got ${JSON.stringify(raw)}`);
  }
  return s;
}

/** Return a deep-cloned ThermalSystem with one nested field updated at `path`. */
export function applyControlValue(system, path, rawValue) {
  if (!system || typeof system !== 'object') {
    throw new Error('system must be an object');
  }
  if (!Array.isArray(path) || path.length === 0) {
    throw new Error('path must be a non-empty array');
  }
  const cloned = structuredClone(system);
  const value = normalizeDecimalInput(rawValue);
  let cursor = cloned;
  for (let i = 0; i < path.length - 1; i += 1) {
    const key = path[i];
    if (cursor === null || typeof cursor !== 'object' || !(key in cursor)) {
      throw new Error(`control path segment ${JSON.stringify(key)} not found`);
    }
    cursor = cursor[key];
  }
  const leaf = path[path.length - 1];
  if (cursor === null || typeof cursor !== 'object' || !(leaf in cursor)) {
    throw new Error(`control leaf ${JSON.stringify(leaf)} not found`);
  }
  cursor[leaf] = value;
  return cloned;
}

/** Enforce honest offline provenance flags on any Python loopback API envelope. */
export function verifyOfflineEnvelope(envelope) {
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) {
    throw new Error('LOOPBACK RESPONSE REFUSED: response must be a JSON object');
  }
  for (const flag of OFFLINE_FLAGS) {
    if (envelope[flag] !== false) {
      throw new Error(`LOOPBACK RESPONSE REFUSED: expected ${flag} === false`);
    }
  }
  if (envelope.ok === true && envelope.result) {
    const r = envelope.result;
    if (r.schema !== 'sim_heat.thermal_result/1') {
      throw new Error(`LOOPBACK RESPONSE REFUSED: unexpected result schema ${r.schema}`);
    }
    for (const flag of OFFLINE_FLAGS) {
      if (r[flag] !== false) {
        throw new Error(`LOOPBACK RESPONSE REFUSED: result.${flag} must be false`);
      }
    }
  }
  return envelope;
}

/**
 * Format an exact rational string ("num" or "num/den" or decimal) to a display decimal
 * string with `places` fractional digits using exact BigInt arithmetic (display only).
 */
export function formatRationalPreview(token, places = 6) {
  if (typeof token !== 'string' || !token.length) {
    return '—';
  }
  if (token.includes('.') && !token.includes('/')) {
    return token;
  }
  const m = RATIONAL_RE.exec(token.trim());
  if (!m) {
    return token;
  }
  let num = BigInt(m[1]);
  const den = m[2] ? BigInt(m[2]) : 1n;
  const neg = num < 0n;
  if (neg) num = -num;
  const scale = 10n ** BigInt(places);
  // Rounded half-up display preview (exact endpoints remain displayed verbatim alongside).
  const scaled = (num * scale * 2n + den) / (den * 2n);
  const whole = scaled / scale;
  if (places === 0) {
    return `${neg ? '-' : ''}${whole.toString()}`;
  }
  const frac = (scaled % scale).toString().padStart(places, '0');
  return `${neg ? '-' : ''}${whole.toString()}.${frac}`;
}

/** Convert an exact rational string to a finite JS number strictly for SVG bar scaling. */
export function rationalToDisplayNumber(token) {
  if (typeof token !== 'string') return NaN;
  const preview = formatRationalPreview(token, 12);
  return Number(preview);
}

/** Format a [lo, hi] exact rational bound pair for human inspection. */
export function formatIntervalPair(pair, unit = '', places = 6) {
  if (!Array.isArray(pair) || pair.length !== 2) return '—';
  const a = formatRationalPreview(pair[0], places);
  const b = formatRationalPreview(pair[1], places);
  const suffix = unit ? ` ${unit}` : '';
  if (a === b) return `${a}${suffix}`;
  return `[${a}, ${b}]${suffix}`;
}

/** Extract normalized display rows for all terminals from a certified sim_heat.thermal_result/1. */
export function extractPortRows(result) {
  if (!result || !result.backendResult) {
    return [];
  }
  const raw = result.backendResult;
  // Staged backend returns substance trajectory + maintainedReservoirTemperaturesK (no raw.ports).
  if (!raw.ports && raw.trajectory && raw.substancePort) {
    const rows = [];
    const traj = raw.trajectory;
    const subPort = raw.substancePort;
    rows.push({
      name: subPort,
      kind: 'staged_phase_substance',
      temperatureDisplay: formatIntervalPair(traj.finalTemperatureBoundsK, 'K', 5),
      exactTemperatureBounds: traj.finalTemperatureBoundsK,
      energyOrPowerDisplay: formatIntervalPair(traj.totalEnergyIntoSubstanceBoundsJ, 'J', 2),
      detailDisplay:
        `${traj.finalStage} (solid ${formatIntervalPair(traj.remainingSolidBoundsKg, 'kg', 4)}, ` +
        `liq ${formatIntervalPair(traj.remainingLiquidBoundsKg, 'kg', 4)})`,
    });
    const maintained = (raw.network && raw.network.maintainedReservoirTemperaturesK) || {};
    for (const [mName, mTemp] of Object.entries(maintained)) {
      const pair = [mTemp, mTemp];
      rows.push({
        name: mName,
        kind: 'maintained',
        temperatureDisplay: formatIntervalPair(pair, 'K', 5),
        exactTemperatureBounds: pair,
        energyOrPowerDisplay: '—',
        detailDisplay: 'maintained reservoir',
      });
    }
    return rows;
  }
  if (!raw.ports) {
    return [];
  }
  const rows = [];
  for (const [name, p] of Object.entries(raw.ports)) {
    const tempPair =
      p.finalTemperatureBoundsK ||
      p.finalBodyTemperatureBoundsK ||
      p.innerFaceTemperatureBoundsK ||
      p.temperatureBoundsK ||
      (p.temperatureK ? [p.temperatureK, p.temperatureK] : null) ||
      (p.transitionTemperatureK ? [p.transitionTemperatureK, p.transitionTemperatureK] : null);
    const outerTempPair = p.outerFaceTemperatureBoundsK || p.outerSurfaceTemperatureBoundsK || null;
    const energyOrPower =
      p.enthalpyChangeBoundsJ
        ? formatIntervalPair(p.enthalpyChangeBoundsJ, 'J', 2)
        : p.latentEnergyIntoBathBoundsJ
          ? formatIntervalPair(p.latentEnergyIntoBathBoundsJ, 'J', 2)
          : p.bodyEnergyChangeBoundsJ
            ? formatIntervalPair(p.bodyEnergyChangeBoundsJ, 'J', 2)
            : p.integratedEnergyIntoReservoirBoundsJ
              ? formatIntervalPair(p.integratedEnergyIntoReservoirBoundsJ, 'J', 2)
              : p.outwardHeatRateBoundsW
                ? formatIntervalPair(p.outwardHeatRateBoundsW, 'W', 4)
                : p.inflowFromNetworkBoundsW
                  ? formatIntervalPair(p.inflowFromNetworkBoundsW, 'W', 4)
                  : '—';
    const phaseNote =
      p.finalMode
        ? `${p.finalMode} (solid ${formatIntervalPair(p.remainingSolidBoundsKg, 'kg', 4)}, liq ${formatIntervalPair(p.remainingLiquidBoundsKg, 'kg', 4)})`
        : p.plateauStatusAtModeledStop
          ? `${p.plateauStatusAtModeledStop} (solid ${formatIntervalPair(p.remainingSolidBoundsKg, 'kg', 4)}, liq ${formatIntervalPair(p.remainingLiquidBoundsKg, 'kg', 4)})`
          : outerTempPair
            ? `outer T_s ${formatIntervalPair(outerTempPair, 'K', 4)}`
            : '—';
    rows.push({
      name,
      kind: p.kind || 'unknown',
      temperatureDisplay: tempPair ? formatIntervalPair(tempPair, 'K', 5) : '—',
      exactTemperatureBounds: tempPair,
      energyOrPowerDisplay: energyOrPower,
      detailDisplay: phaseNote,
    });
  }
  return rows;
}

/** Build SVG bar chart descriptors strictly from Python-returned critical-radius sweep results. */
export function buildSweepBarModel(sweepPoints) {
  if (!Array.isArray(sweepPoints) || sweepPoints.length === 0) return [];
  const parsed = sweepPoints.map((pt) => {
    const lo = rationalToDisplayNumber(pt.heatLossBoundsW[0]);
    const hi = rationalToDisplayNumber(pt.heatLossBoundsW[1]);
    const mid = (lo + hi) / 2;
    return {
      radiusM: pt.radiusM,
      lo,
      hi,
      mid,
      negative: mid < 0,
      label: formatIntervalPair(pt.heatLossBoundsW, 'W', 3),
    };
  });
  const maxAbs = Math.max(...parsed.map((p) => Math.max(Math.abs(p.lo), Math.abs(p.hi))), 0);
  const denom = maxAbs > 0 ? maxAbs : 1;
  return parsed.map((p) => ({
    ...p,
    barFraction: Math.max(0, Math.min(1, Math.abs(p.mid) / denom)),
  }));
}
