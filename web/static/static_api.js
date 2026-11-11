// Static-site data layer: answers api() calls without the Python server.
// GET paths come from the JSON exported by scripts/build_static.py; POST /analyze runs the JS port (dac_engine.js),
// which is tested against the Python core (dac_engine.test.mjs).
import { analyseText } from './dac_engine.js';

const files = new Map();
function file(rel) {
  if (!files.has(rel)) files.set(rel, fetch('api/' + rel + '.json').then(r => { if (!r.ok) throw new Error(`${r.status} ${rel}`); return r.json(); }));
  return files.get(rel);
}

export async function staticApi(path, body) {
  const clean = path.split('?')[0].replace(/^\/+/, '');
  if (clean === 'analyze') {
    const f = body && body.get('file');
    if (!f) throw new Error('No file given.');
    if (!/\.csv$/i.test(f.name)) throw new Error('Excel files need the local app (Python). On this site, save the sheet as CSV first.');
    return analyseText(await f.text(), body.get('time_interval'), body.get('num_intervals'), f.name);
  }
  return file(clean);
}
