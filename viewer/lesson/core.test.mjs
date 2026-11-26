import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  applyControlValue,
  buildSweepBarModel,
  extractPortRows,
  formatIntervalPair,
  formatRationalPreview,
  normalizeDecimalInput,
  verifyOfflineEnvelope,
} from './core.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));

test('normalizeDecimalInput accepts strict unsigned SI decimals and rejects scientific/signed', () => {
  assert.equal(normalizeDecimalInput('273.15'), '273.15');
  assert.equal(normalizeDecimalInput('0'), '0');
  assert.equal(normalizeDecimalInput('0.08'), '0.08');
  for (const bad of ['-1', '+1', '1e-3', '1/2', 'NaN', '', '01']) {
    assert.throws(() => normalizeDecimalInput(bad));
  }
});

test('applyControlValue immutably updates nested system fields', () => {
  const sys = {
    schema: 'sim_heat.thermal_system/1',
    attachments: { vessel_in: { geometry: { layers: [{ outerRadiusM: '0.08' }] } } },
  };
  const next = applyControlValue(sys, ['attachments', 'vessel_in', 'geometry', 'layers', 0, 'outerRadiusM'], '0.12');
  assert.equal(sys.attachments.vessel_in.geometry.layers[0].outerRadiusM, '0.08');
  assert.equal(next.attachments.vessel_in.geometry.layers[0].outerRadiusM, '0.12');
});

test('verifyOfflineEnvelope enforces honest False flags and refuses forged promotion', () => {
  const good = {
    ok: true,
    nativeExecuted: false,
    nativeQualified: false,
    independentlyCertifiedReference: false,
    runnerConsumable: false,
    result: {
      schema: 'sim_heat.thermal_result/1',
      nativeExecuted: false,
      nativeQualified: false,
      independentlyCertifiedReference: false,
      runnerConsumable: false,
    },
  };
  assert.equal(verifyOfflineEnvelope(good), good);

  for (const flag of ['nativeExecuted', 'nativeQualified', 'independentlyCertifiedReference', 'runnerConsumable']) {
    const forgedTop = { ...good, [flag]: true };
    assert.throws(() => verifyOfflineEnvelope(forgedTop), /REFUSED/);
    const forgedInner = { ...good, result: { ...good.result, [flag]: true } };
    assert.throws(() => verifyOfflineEnvelope(forgedInner), /REFUSED/);
  }
});

test('formatRationalPreview and formatIntervalPair use exact BigInt display formatting', () => {
  assert.equal(formatRationalPreview('1/3', 6), '0.333333');
  assert.equal(formatRationalPreview('-5/2', 2), '-2.50');
  assert.equal(formatIntervalPair(['27315/100', '27315/100'], 'K', 2), '273.15 K');
  assert.equal(formatIntervalPair(['100', '101'], 'W', 1), '[100.0, 101.0] W');
});

test('extractPortRows and buildSweepBarModel strictly reflect Python payloads', () => {
  const rows = extractPortRows({
    backendResult: {
      ports: {
        vessel_in: {
          kind: 'radial_shell',
          innerFaceTemperatureBoundsK: ['399', '399'],
          outerFaceTemperatureBoundsK: ['350', '350'],
          outwardHeatRateBoundsW: ['40', '40'],
        },
      },
    },
  });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].name, 'vessel_in');
  assert.match(rows[0].energyOrPowerDisplay, /40\.0000 W/);

  const bars = buildSweepBarModel([
    { radiusM: '0.045', heatLossBoundsW: ['25', '25'] },
    { radiusM: '0.08', heatLossBoundsW: ['50', '50'] },
  ]);
  assert.equal(bars.length, 2);
  assert.equal(bars[1].barFraction, 1);
  assert.equal(bars[0].barFraction, 0.5);
});

test('architectural invariant: zero second physics implementation in viewer/lesson JavaScript', () => {
  const forbiddenPatterns = [
    /\bMath\.exp\b/,
    /\bMath\.log\b/,
    /\bMath\.pow\b/,
    /\bMath\.sqrt\b/,
    /\bstep_matrix\b/,
    /\bschur\b/i,
    /5\.67e-8/i,
  ];
  for (const file of ['core.mjs', 'app.mjs']) {
    const src = fs.readFileSync(path.join(HERE, file), 'utf8');
    for (const re of forbiddenPatterns) {
      assert.doesNotMatch(src, re, `${file} must not contain physics math pattern ${re}`);
    }
  }
});
