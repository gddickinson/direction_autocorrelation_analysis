// node web/static/dac_engine.test.mjs
// Asserts the JS port (dac_engine.js) reproduces the repo's Python analysis (io_utils.read_file + core.process_sheet)
// on the inputs in tests/fixtures/dac_fixture.json (regenerate with: python scripts/make_dac_fixture.py).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { analyseText, maxDifference, parseCSV, splitSheets, identifyColumns } from './dac_engine.js';
import { simulateCSV, theoryCurve } from './dac_sim.js';

const TOL = 1e-9;
const fx = JSON.parse(readFileSync(new URL('../../tests/fixtures/dac_fixture.json', import.meta.url)));
let worstAll = 0, values = 0;
for (const c of fx.cases) {
  const got = analyseText(c.csv, c.time_interval, c.num_intervals, c.name + '.csv');
  const exp = c.expected;
  assert.equal(got.conditions.length, exp.conditions.length, c.name);
  got.conditions.forEach((g, i) => {
    const e = exp.conditions[i];
    assert.equal(String(g.name), String(e.name));
    for (const k of ['n_rows', 'n_dropped', 'n_segments']) assert.equal(g[k], e[k], `${c.name}/${g.name} ${k}`);
    assert.deepEqual(g.n_pairs, e.n_pairs, `${c.name}/${g.name} n_pairs`);
    assert.deepEqual(g.tracks.map(t => t.id), e.tracks.map(t => t.id), `${c.name}/${g.name} track ids`);
    values += g.avg.length * 2 + g.tracks.reduce((s, t) => s + t.c.length, 0);
  });
  const d = maxDifference(got, exp);
  console.log(`${c.name}: ${got.conditions.length} condition(s), max |JS - Python| = ${d.toExponential(2)}`);
  assert.ok(d <= TOL, `${c.name}: difference ${d} > ${TOL}`);
  worstAll = Math.max(worstAll, d);
}

// Conventions spelled out in core.py that the port must keep.
const r = analyseText('frame,x,y\n1,0,0\n2,1,0\n3,2,0\n4,3,0\n5,4,0\n', 1, 4);
const s = r.conditions[0];
assert.deepEqual(s.lags, [0, 1, 2, 3, 4]);
assert.deepEqual(s.avg.slice(0, 4), [1, 1, 1, 1]);
assert.equal(s.avg[4], null, 'last lag is never computed (step < num_intervals)');
assert.equal(s.sem[4], 0);
assert.equal(identifyColumns(['a', 'b']), null);
assert.equal(splitSheets(parseCSV('Group,frame,x,y\nB,1,0,0\nA,1,0,0\n')).map(x => x.name).join(), 'A,B');

// Simulator: reproducible, parseable, and the theory curve starts at 1.
const sim1 = simulateCSV({ seed: 3 }), sim2 = simulateCSV({ seed: 3 });
assert.equal(sim1, sim2);
assert.ok(analyseText(sim1, 1, 10).conditions.every(c => !c.error && c.avg[1] > 0));
assert.equal(theoryCurve(0.5, [0, 1])[0], 1);

console.log(`dac_engine: ${fx.cases.length} fixture cases, ${values} values, worst |JS - Python| = ${worstAll.toExponential(2)} (tol ${TOL}) ok`);
