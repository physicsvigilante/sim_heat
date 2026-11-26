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
  assert.equal(formatRationalPreview('3/2', 0), '2');
  assert.equal(formatIntervalPair(['27315/100', '27315/100'], 'K', 2), '273.15 K');
  assert.equal(formatIntervalPair(['100', '101'], 'W', 1), '[100.0, 101.0] W');
});

test('extractPortRows covers multiport, staged, and multibody phase_bath backends cleanly', () => {
  const mpRows = extractPortRows({
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
  assert.equal(mpRows.length, 1);
  assert.equal(mpRows[0].name, 'vessel_in');
  assert.match(mpRows[0].energyOrPowerDisplay, /40\.0000 W/);

  // M05-R01: staged backend (trajectory + maintainedReservoirTemperaturesK, no ports)
  const stRows = extractPortRows({
    backendResult: {
      substancePort: 'sample',
      network: { maintainedReservoirTemperaturesK: { cryostat: '210' } },
      trajectory: {
        finalStage: 'solid_sensible',
        finalTemperatureBoundsK: ['220', '221'],
        totalEnergyIntoSubstanceBoundsJ: ['-35000', '-34900'],
        remainingSolidBoundsKg: ['8/100', '8/100'],
        remainingLiquidBoundsKg: ['0', '0'],
      },
    },
  });
  assert.equal(stRows.length, 2);
  assert.equal(stRows[0].name, 'sample');
  assert.equal(stRows[0].kind, 'staged_phase_substance');
  assert.match(stRows[0].temperatureDisplay, /220\.00000/);
  assert.match(stRows[0].detailDisplay, /solid_sensible/);
  assert.equal(stRows[1].name, 'cryostat');
  assert.equal(stRows[1].temperatureDisplay, '210.00000 K');

  // M05-R01: multibody phase_bath port (transitionTemperatureK + latentEnergyIntoBathBoundsJ)
  const mbRows = extractPortRows({
    backendResult: {
      ports: {
        ice: {
          kind: 'phase_bath',
          transitionTemperatureK: '273.15',
          latentEnergyIntoBathBoundsJ: ['1500', '1501'],
          plateauStatusAtModeledStop: 'coexisting',
          remainingSolidBoundsKg: ['1/2', '1/2'],
          remainingLiquidBoundsKg: ['1/4', '1/4'],
        },
      },
    },
  });
  assert.equal(mbRows.length, 1);
  assert.equal(mbRows[0].temperatureDisplay, '273.15 K');
  assert.match(mbRows[0].energyOrPowerDisplay, /1500\.00/);
  assert.match(mbRows[0].detailDisplay, /coexisting.*solid/);

  // M06: stefan backend (stefan + maintainedReservoirTemperaturesK, no ports)
  const sfRows = extractPortRows({
    backendResult: {
      network: { stefanPort: 'ice_face', maintainedReservoirTemperaturesK: { air: '263.15' } },
      stefan: {
        geometry: 'planar',
        status: 'growing',
        finalPortTemperatureBoundsK: ['265', '265'],
        latentEnergyIntoLayerBoundsJ: ['-150000', '-150000'],
        finalSolidThicknessBoundsM: ['1/20', '1/20'],
        finalSolidMassBoundsKg: ['4585/100', '4585/100'],
      },
    },
  });
  assert.equal(sfRows.length, 2);
  assert.equal(sfRows[0].name, 'ice_face');
  assert.equal(sfRows[0].kind, 'stefan_layer (planar)');
  assert.match(sfRows[0].detailDisplay, /growing.*thickness 0\.05000 m/);
  assert.equal(sfRows[1].name, 'air');
  assert.equal(sfRows[1].temperatureDisplay, '263.15 K');

  // M07: radiative_transient radial_shell cumulativeOutwardEnergyBoundsJ display row
  const rtRows = extractPortRows({
    backendResult: {
      ports: {
        shell_in: {
          kind: 'radial_shell',
          innerFaceTemperatureBoundsK: ['420', '421'],
          outerFaceTemperatureBoundsK: ['380', '381'],
          cumulativeOutwardEnergyBoundsJ: ['12500', '12550'],
        },
      },
    },
  });
  assert.equal(rtRows.length, 1);
  assert.equal(rtRows[0].name, 'shell_in');
  assert.match(rtRows[0].energyOrPowerDisplay, /12500\.00/);
  assert.match(rtRows[0].detailDisplay, /outer T_s/);

  // M05-R04: buildSweepBarModel handles sub-watt and negative heat rates cleanly
  const bars = buildSweepBarModel([
    { radiusM: '0.045', heatLossBoundsW: ['25', '25'] },
    { radiusM: '0.08', heatLossBoundsW: ['50', '50'] },
  ]);
  assert.equal(bars.length, 2);
  assert.equal(bars[1].barFraction, 1);
  assert.equal(bars[0].barFraction, 0.5);

  const smallBars = buildSweepBarModel([
    { radiusM: '0.05', heatLossBoundsW: ['1/100', '1/100'] },
    { radiusM: '0.10', heatLossBoundsW: ['1/50', '1/50'] },
  ]);
  assert.equal(smallBars[1].barFraction, 1);
  assert.equal(smallBars[0].barFraction, 0.5);
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
