/** Read-only comparison of two admitted *display* schemas, not source custody.
 *
 * No native runs, predicted values, flow/temperature arithmetic or
 * apparatus-specific composition. Both payloads are separately validated.
 */
import {admitPreview} from './core.mjs';

const identical = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const byId = values => new Map(values.map(value => [value.id, value]));
const sortedUnion = (a, b) => [...new Set([...a.keys(), ...b.keys()])].sort();
const inputMap = component => new Map((component?.inputs ?? []).map(input => [input.name, input]));
const sourceNotes = component => component ? ({input: component.sourceProvenance, component: component.componentProvenance}) : null;
const nodePortSignature = (preview, id) => {
  const node = preview.nodes.find(n => n.id === id);
  if (!node) throw Error('SOURCE COMPARISON REFUSED: missing logical node');
  return [...node.ports].sort().join(' + ');
};
const modelShape = preview => ({
  modelName: preview.modelName,
  components: [...preview.components].sort((a, b) => a.id.localeCompare(b.id))
    .map(c => ({id: c.id, kind: c.kind, inputs: [...c.inputs]
      .sort((a, b) => a.name.localeCompare(b.name))
      .map(x => [x.name, x.quantityType, x.siUnit, x.sourceValue])})),
  physicalGroups: preview.nodes.map(n => [...n.ports].sort().join(' + ')).sort(),
  rods: [...preview.rods].sort((a, b) => a.id.localeCompare(b.id))
    .map(r => [r.id, nodePortSignature(preview, r.from), nodePortSignature(preview, r.to)]),
});
const studyShape = preview => ({
  modelShape: modelShape(preview), modelSha256: preview.source.modelSha256,
  studyId: preview.studyId, mode: preview.mode,
  requests: preview.requests, modelProvenance: preview.modelProvenance,
  sourceProvenance: [...preview.components].sort((a, b) => a.id.localeCompare(b.id))
    .map(c => [c.id, sourceNotes(c)]),
});

/** Differences represent changes in AUTHORED facts and logical wiring only. */
export function compareSourcePreviews(left, right) {
  const baseline = admitPreview(left);
  const variant = admitPreview(right);
  if (baseline.source.modelSha256 === variant.source.modelSha256 &&
      !identical(modelShape(baseline), modelShape(variant))) {
    throw Error('SOURCE COMPARISON REFUSED: differing model facts share a model SHA-256');
  }
  if (baseline.source.studySha256 === variant.source.studySha256 &&
      !identical(studyShape(baseline), studyShape(variant))) {
    throw Error('SOURCE COMPARISON REFUSED: differing study facts share a study SHA-256');
  }
  const changes = [];
  const add = (category, label, from, to) => {
    changes.push({category, label, from: String(from), to: String(to)});
  };
  if (baseline.modelName !== variant.modelName)
    add('model', 'Authored model name', baseline.modelName, variant.modelName);
  if (baseline.mode !== variant.mode)
    add('assumption', 'Authored regime', baseline.mode, variant.mode);
  const aComponents = byId(baseline.components), bComponents = byId(variant.components);
  for (const id of sortedUnion(aComponents, bComponents)) {
    const a = aComponents.get(id), b = bComponents.get(id);
    if (!a || !b) {
      add('component', id, a ? a.kind : 'not present', b ? b.kind : 'not present');
    } else if (a.kind !== b.kind) {
      add('component', id + ' · kind', a.kind, b.kind);
    }
    // Never omit authored SI fields or source attribution when the entire
    // physical component has been added, removed or changed law/type.
    const aInputs = inputMap(a), bInputs = inputMap(b);
    for (const name of sortedUnion(aInputs, bInputs)) {
      const old = aInputs.get(name), next = bInputs.get(name);
      const show = x => x ? `${x.sourceValue} ${x.siUnit} (${x.quantityType})` : 'not present';
      if (!old || !next || old.sourceValue !== next.sourceValue ||
          old.quantityType !== next.quantityType || old.siUnit !== next.siUnit) {
        add('input', `${id}.${name} · authored SI`, show(old), show(next));
      }
    }
    if (!identical(sourceNotes(a), sourceNotes(b)))
      add('provenance', id + ' · original attribution / assumptions',
          a ? JSON.stringify(sourceNotes(a)) : 'not present',
          b ? JSON.stringify(sourceNotes(b)) : 'not present');
  }
  // Compare physical port groups, never generated node_0 indexes or positions.
  const ports = p => p.nodes.map(n => [...n.ports].sort().join(' + ')).sort();
  if (!identical(ports(baseline), ports(variant)))
    add('topology', 'Physical port groups (not spatial geometry)',
        ports(baseline).join(' | '), ports(variant).join(' | '));
  const aRods = byId(baseline.rods), bRods = byId(variant.rods);
  for (const id of sortedUnion(aRods, bRods)) {
    const a = aRods.get(id), b = bRods.get(id);
    const label = (p, r) => r ?
      `${nodePortSignature(p, r.from)} ⇄ ${nodePortSignature(p, r.to)}` : 'not present';
    if (!a || !b || label(baseline, a) !== label(variant, b))
      add('connection', id + ' · logical rod ends', label(baseline, a), label(variant, b));
  }
  const aRequests = byId(baseline.requests), bRequests = byId(variant.requests);
  for (const id of sortedUnion(aRequests, bRequests)) {
    const a = aRequests.get(id), b = bRequests.get(id);
    const desc = r => r ? `${r.operation} · ${r.targets.join(' → ')} · ${r.unit} · not_computed` : 'not present';
    if (!identical(a, b)) add('request', id, desc(a), desc(b));
  }
  if (!identical(baseline.modelProvenance, variant.modelProvenance))
    add('assumption', 'Original @model provenance',
        JSON.stringify(baseline.modelProvenance), JSON.stringify(variant.modelProvenance));
  const inventory = p => ({components:p.components.length, rods:p.rods.length,
    bodies:p.nodes.filter(n => n.role === 'body').length,
    boundaries:p.nodes.filter(n => n.role === 'boundary').length,
    junctions:p.nodes.filter(n => n.role === 'junction').length});
  return {
    schema: 'sim_heat.viewer.authored_source_comparison/1',
    status: 'source_facts_only_not_simulated',
    sourceFidelityIndependentlyQualified: false,
    nativeExecuted: false, nativeQualified: false,
    publicRequestStatus: 'not_computed',
    baseline: {studyId:baseline.studyId, modelSha256:baseline.source.modelSha256,
      studySha256:baseline.source.studySha256, inventory:inventory(baseline)},
    variant: {studyId:variant.studyId, modelSha256:variant.source.modelSha256,
      studySha256:variant.source.studySha256, inventory:inventory(variant)},
    changes,
    disclaimer:'Changes are only in admitted/claimed authored source; no physical trajectory, heat flow or answer is calculated.',
  };
}
