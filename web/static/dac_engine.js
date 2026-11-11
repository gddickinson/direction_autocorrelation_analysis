// Direction autocorrelation engine: a pure-JS port of the repo's Python analysis, used on the static site.
// Mirrors io_utils.read_file (CSV branch), io_utils.identify_columns and core.process_sheet
// (calculate_normed_vectors -> calculate_scalar_products -> calculate_averages), including their conventions:
//  - a new trajectory starts wherever the frame number does not increase (frame[i] - frame[i-1] <= 0);
//  - the unit vector stored on row k is (r[k-1] - r[k]) / |r[k-1] - r[k]| (first row of a track has none; zero steps
//    give NaN and are skipped);
//  - lags are time_interval * step for step = 1..num_intervals; a track of L points contributes to steps up to
//    min(num_intervals, L - 2) (L - 1 vectors); a lag with no pairs has AVG NaN, SEM 0;
//  - SEM = sample std (ddof 1) / sqrt(n) of the pooled scalar products; lag 0 is fixed at AVG 1, SEM 0.
// Rows with missing frame/x/y are dropped and positions are re-indexed 0..n-1 (see web/analysis.py for why).
// The output has the same JSON shape as POST /api/analyze. Tested against Python in dac_engine.test.mjs.

export const COLUMN_OPTIONS = {
  frame: ['frame', 'frames', 'frame_number', 'frameno', 'time', 'f', '#frame'],
  x: ['x', 'x_coord', 'x_coordinate', 'xpos', 'x_position', 'x-position', 'x position'],
  y: ['y', 'y_coord', 'y_coordinate', 'ypos', 'y_position', 'y-position', 'y position'],
};
export const SHEET_COLUMNS = ['sheet', 'condition', 'group', 'experiment'];
export const MAX_SEGMENTS_RETURNED = 300;

// Minimal RFC-4180 CSV reader: quoted fields, "" escapes, CRLF; blank lines skipped (as pandas does).
export function parseCSV(text) {
  const rows = [];
  let row = [], field = '', q = false;
  const s = String(text).replace(/^﻿/, '');
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) {
      if (c === '"') { if (s[i + 1] === '"') { field += '"'; i++; } else q = false; } else field += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && s[i + 1] === '\n') i++;
      row.push(field); field = '';
      if (row.length > 1 || row[0] !== '') rows.push(row);
      row = [];
    } else field += c;
  }
  row.push(field);
  if (row.length > 1 || row[0] !== '') rows.push(row);
  if (!rows.length) throw new Error('The file is empty.');
  return { header: rows[0], rows: rows.slice(1) };
}

// Strings pandas.read_csv reads as missing (its default na_values).
const NA = new Set(['', '#N/A', '#N/A N/A', '#NA', '-1.#IND', '-1.#QNAN', '-NaN', '-nan', '1.#IND', '1.#QNAN', '<NA>', 'N/A',
  'NA', 'NULL', 'NaN', 'None', 'n/a', 'nan', 'null']);
const toNum = v => { const t = String(v ?? '').trim(); return NA.has(t) ? NaN : Number(t); };

// Split into sheets on a sheet/condition/group/experiment column (case-insensitive), as read_file does for CSVs.
// Groups are sorted like pandas groupby (numerically if every key is a number) and rows with no key are dropped.
export function splitSheets({ header, rows }) {
  let k = -1;
  for (const opt of SHEET_COLUMNS) { k = header.findIndex(h => h.toLowerCase() === opt); if (k >= 0) break; }
  if (k < 0) return [{ name: 'Sheet1', header, rows }];
  const sub = header.filter((_, i) => i !== k), groups = new Map();
  const raw = rows.map(r => r[k] ?? ''), isNA = raw.map(v => NA.has(v.trim()));
  // A numeric key column is read as numbers ('02' -> 2): int names ('2') unless a key is missing or fractional,
  // when pandas uses floats ('2.0', '2.5').
  const present = raw.filter((_, i) => !isNA[i]);
  const numeric = present.length > 0 && present.every(v => v.trim() !== '' && Number.isFinite(Number(v)));
  const floats = numeric && (isNA.some(Boolean) || present.some(v => !Number.isInteger(Number(v))));
  const norm = v => (!numeric ? v : floats && Number.isInteger(Number(v)) ? Number(v).toFixed(1) : String(Number(v)));
  rows.forEach((r, i) => {
    if (isNA[i]) return;
    const key = norm(raw[i]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r.filter((_, j) => j !== k));
  });
  const keys = [...groups.keys()];
  keys.sort(numeric ? (a, b) => Number(a) - Number(b) : (a, b) => (a < b ? -1 : a > b ? 1 : 0));
  return keys.map(name => ({ name, header: sub, rows: groups.get(name) }));
}

// identify_columns: first matching alias (case-insensitive; the last duplicate header wins), else columns 4/5/6
// (1-based) when the sheet has at least 6 columns. Returns column indices or null.
export function identifyColumns(header) {
  const lower = new Map();
  header.forEach((h, i) => lower.set(h.toLowerCase(), i));
  const pick = opts => { for (const o of opts) if (lower.has(o)) return lower.get(o); return null; };
  let f = pick(COLUMN_OPTIONS.frame), x = pick(COLUMN_OPTIONS.x), y = pick(COLUMN_OPTIONS.y);
  if ((f === null || x === null || y === null) && header.length >= 6) { f ??= 3; x ??= 4; y ??= 5; }
  if (f === null || x === null || y === null) return null;
  return { frame: f, x, y, names: { frame: header[f], x: header[x], y: header[y] } };
}

const mean = a => { let s = 0; for (const v of a) s += v; return s / a.length; };
function sem(a) {
  const n = a.length;
  if (n === 0) return 0;
  if (n === 1) return NaN;
  const m = mean(a);
  let ss = 0;
  for (const v of a) ss += (v - m) * (v - m);
  return Math.sqrt(ss / (n - 1)) / Math.sqrt(n);
}

// Trajectory boundaries (positions): starts of each segment plus the end.
export function trajectoryStarts(frame) {
  if (!frame.length) return [0];
  const s = [0];
  for (let i = 1; i < frame.length; i++) if (frame[i] - frame[i - 1] <= 0) s.push(i);
  s.push(frame.length);
  return s;
}

// calculate_normed_vectors
export function normedVectors(x, y, starts) {
  const n = x.length, vx = new Float64Array(n).fill(NaN), vy = new Float64Array(n).fill(NaN);
  for (let i = 0; i < starts.length - 1; i++) {
    const a = starts[i], b = starts[i + 1];
    if (b - a < 2) continue;
    for (let k = a + 1; k < b; k++) {
      const dx = x[k - 1] - x[k], dy = y[k - 1] - y[k], m = Math.sqrt(dx * dx + dy * dy);
      if (m > 0) { vx[k] = dx / m; vy[k] = dy / m; }
    }
  }
  return { vx, vy };
}

// calculate_scalar_products + calculate_averages on clean numeric arrays.
export function processArrays(frame, x, y, timeInterval, numIntervals) {
  const starts = trajectoryStarts(frame);
  const { vx, vy } = normedVectors(x, y, starts);
  const pooled = Array.from({ length: numIntervals }, () => []);
  const tracks = [];
  for (let i = 0; i < starts.length - 1; i++) {
    const a = starts[i], b = starts[i + 1], len = b - a;
    if (len < 2) continue;
    const tr = { id: `track_${i + 1}`, t: [], c: [] };
    const maxStep = Math.min(numIntervals, len - 2);
    for (let step = 1; step <= maxStep; step++) {
      const dots = [];
      for (let j = a; j < b - step; j++) {
        const d = vx[j] * vx[j + step] + vy[j] * vy[j + step];
        if (!Number.isNaN(d)) dots.push(d);
      }
      for (const d of dots) pooled[step - 1].push(d);
      if (dots.length) { tr.t.push(timeInterval * step); tr.c.push(mean(dots)); }
    }
    if (tr.t.length) tracks.push(tr);
  }
  const lags = [0], avg = [1], sems = [0], nPairs = [0];
  pooled.forEach((v, k) => {
    lags.push(timeInterval * (k + 1));
    avg.push(v.length ? mean(v) : NaN); sems.push(sem(v)); nPairs.push(v.length);
  });
  return { starts, lags, avg, sem: sems, n_pairs: nPairs, tracks };
}

const clean = v => (Number.isFinite(v) ? v : null);

// One sheet: identify columns, drop incomplete rows, analyse. Same JSON shape as web/analysis.py analyse_sheet.
export function analyseSheet(sheet, timeInterval, numIntervals) {
  const cols = identifyColumns(sheet.header);
  if (!cols) return { name: sheet.name, error: 'Could not find frame, x and y columns (see the data format page).' };
  const frame = [], x = [], y = [];
  for (const r of sheet.rows) {
    const f = toNum(r[cols.frame]), a = toNum(r[cols.x]), b = toNum(r[cols.y]);
    if (Number.isNaN(f) || Number.isNaN(a) || Number.isNaN(b)) continue;
    frame.push(f); x.push(a); y.push(b);
  }
  const res = processArrays(frame, x, y, timeInterval, numIntervals);
  const segments = [];
  for (let i = 0; i < Math.min(res.starts.length - 1, MAX_SEGMENTS_RETURNED); i++) {
    const a = res.starts[i], b = res.starts[i + 1];
    segments.push({ id: `track_${i + 1}`, x: x.slice(a, b), y: y.slice(a, b) });
  }
  return {
    name: sheet.name, n_rows: sheet.rows.length, n_dropped: sheet.rows.length - frame.length,
    n_segments: frame.length ? res.starts.length - 1 : 0,
    lags: res.lags, avg: res.avg.map(clean), sem: res.sem.map(clean), n_pairs: res.n_pairs,
    tracks: res.tracks.map(t => ({ id: t.id, t: t.t, c: t.c.map(clean) })), segments,
  };
}

// Whole CSV text -> result object (as POST /api/analyze returns, with engine 'js').
export function analyseText(text, timeInterval, numIntervals, file = 'data.csv') {
  timeInterval = Number(timeInterval); numIntervals = Math.trunc(Number(numIntervals));
  if (!(timeInterval > 0) || !(numIntervals >= 1)) throw new Error('time_interval must be > 0 and num_intervals >= 1');
  const sheets = splitSheets(parseCSV(text));
  return { engine: 'js', file, time_interval: timeInterval, num_intervals: numIntervals,
    conditions: sheets.map(s => analyseSheet(s, timeInterval, numIntervals)) };
}

// Largest absolute difference between two results (avg, sem, n_pairs, per-track correlations); null-vs-number = Infinity.
export function maxDifference(a, b) {
  let worst = 0;
  const cmp = (p, q) => {
    if (p === null || q === null) { if (p !== q) worst = Infinity; return; }
    worst = Math.max(worst, Math.abs(p - q));
  };
  const arr = (p, q) => { if (p.length !== q.length) { worst = Infinity; return; } p.forEach((v, i) => cmp(v, q[i])); };
  if (a.conditions.length !== b.conditions.length) return Infinity;
  a.conditions.forEach((ca, i) => {
    const cb = b.conditions[i];
    if (String(ca.name) !== String(cb.name) || !!ca.error !== !!cb.error) { worst = Infinity; return; }
    if (ca.error) return;
    arr(ca.lags, cb.lags); arr(ca.avg, cb.avg); arr(ca.sem, cb.sem); arr(ca.n_pairs, cb.n_pairs);
    if (ca.tracks.length !== cb.tracks.length) { worst = Infinity; return; }
    ca.tracks.forEach((t, k) => {
      const u = cb.tracks[k];
      if (t.id !== u.id) { worst = Infinity; return; }
      arr(t.t, u.t); arr(t.c, u.c);
    });
  });
  return worst;
}
