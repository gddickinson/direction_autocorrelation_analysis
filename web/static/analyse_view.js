// Results view for the analysis page: tiles, trajectory map, autocorrelation curve with SEM error bars, summary table,
// CSV export. res has the shape returned by POST /api/analyze (Python) or dac_engine.analyseText (JS).
import { esc, download } from './core.js';
import { linePlot, trajectoryPlot, COLORS } from './dac_plots.js';
import { summaryCSV, tracksCSV } from './dac_export.js';
import { DEMO, theoryCurve } from './dac_sim.js';

const f3 = v => (v === null || v === undefined ? '—' : v.toFixed(3));
const fmtLag = v => String(+v.toPrecision(10));

export function renderResults(host, res, meta) {
  const ok = res.conditions.filter(c => !c.error);
  const bad = res.conditions.filter(c => c.error);
  const unit = meta.timeUnit;
  const nSeg = ok.reduce((s, c) => s + c.n_segments, 0), nPts = ok.reduce((s, c) => s + c.n_rows - c.n_dropped, 0);
  const dropped = ok.filter(c => c.n_dropped > 0);
  const notes = [];
  if (meta.simulated) notes.push('<span class="sim-badge">SIMULATED</span> These results are from simulated persistent random walks, not measurements. Dashed lines show the expected curve exp(−m σ²/2) for a lag of m frames.');
  bad.forEach(c => notes.push(`<span class="err">${esc(c.name)}: ${esc(c.error)}</span>`));
  dropped.forEach(c => notes.push(`${esc(c.name)}: ${c.n_dropped} row(s) with a missing frame, x or y value were dropped.`));
  notes.push(`As in the Python code, lags are computed for steps shorter than the number of intervals, so the last lag (${fmtLag(res.time_interval * res.num_intervals)} ${esc(unit)}) is always empty.`);
  if (meta.check !== null && meta.check !== undefined) {
    notes.push(Number.isFinite(meta.check) && meta.check < 1e-9
      ? `<span class="ok">Cross-check:</span> the in-browser JS port gives the same numbers as Python here (largest difference ${meta.check.toExponential(1)}).`
      : `<span class="err">Cross-check:</span> the JS port differs from Python on this file (${meta.check}); the Python numbers are shown.`);
  }
  host.innerHTML = `<h2>Results</h2>
    <div class="tiles"><div class="tile"><b>${ok.length}</b><span>condition${ok.length === 1 ? '' : 's'}</span></div>
      <div class="tile"><b>${nSeg}</b><span>trajectories (frame resets)</span></div>
      <div class="tile"><b>${nPts}</b><span>positions analysed</span></div>
      <div class="tile"><b>${res.engine === 'python' ? 'Python' : 'JS'}</b><span>engine</span></div></div>
    ${notes.map(n => `<p class="small">${n}</p>`).join('')}
    ${ok.length ? `<div class="two">
      <div class="panel"><h3 style="margin-top:0">Trajectories</h3>
        <label for="v-cond">Condition</label><select id="v-cond">${ok.map((c, i) => `<option value="${i}">${esc(c.name)}</option>`).join('')}</select>
        <div id="p-traj"></div><p id="traj-note" class="small mute"></p></div>
      <div class="panel"><h3 style="margin-top:0">Direction autocorrelation</h3>
        <label><input id="v-tracks" type="checkbox"> show individual tracks of the selected condition</label>
        <div id="p-ac"></div><p class="small mute">Mean of the pooled scalar products of unit direction vectors ± SEM (error bars).</p></div></div>
    <div class="panel"><h3 style="margin-top:0">Summary table</h3>
      <p class="small mute">AVG ± SEM of the direction autocorrelation per time lag; n = number of scalar products pooled across tracks.</p>
      <div class="scroll" id="t-sum"></div>
      <button id="x-sum" type="button">Export summary CSV</button><button id="x-tr" class="alt" type="button">Export per-track CSV</button></div>` : ''}`;
  if (!ok.length) return;

  const sel = host.querySelector('#v-cond'), showTracks = host.querySelector('#v-tracks');
  const draw = () => {
    const i = +sel.value, c = ok[i], k = meta.coordUnit === 'px' ? meta.pixelSize : 1;
    const segs = c.segments.slice(0, meta.maxTracks).map(s => ({ x: s.x.map(v => v * k), y: s.y.map(v => v * k) }));
    trajectoryPlot(host.querySelector('#p-traj'), segs, { color: COLORS[i % COLORS.length], title: `Trajectories of ${c.name}` });
    host.querySelector('#traj-note').textContent = `${segs.length} of ${c.n_segments} trajectories shown (first ${meta.maxTracks}, the plot limit in config.py). `
      + (meta.coordUnit === 'px' ? `Pixels × ${meta.pixelSize} µm/px.` : 'Coordinates in µm as given.') + ' Dots mark track starts.';
    const series = [];
    if (showTracks.checked) c.tracks.forEach(t => series.push({ x: t.t, y: t.c, color: COLORS[i % COLORS.length], width: 1, opacity: 0.18 }));
    ok.forEach((cc, j) => {
      series.push({ x: cc.lags, y: cc.avg, err: cc.sem, color: COLORS[j % COLORS.length], label: cc.name, width: 2.4, dots: true });
      const sim = meta.simulated && DEMO.conditions.find(dc => dc.name === cc.name);
      if (sim) series.push({ x: cc.lags, y: theoryCurve(sim.sigma, cc.lags.map(l => l / res.time_interval)), color: COLORS[j % COLORS.length], dash: '6 5', width: 1.5, label: `expected, ${cc.name}` });
    });
    const lows = ok.flatMap(cc => cc.avg.map((a, n) => (a === null ? 0 : a - (cc.sem[n] || 0))));
    linePlot(host.querySelector('#p-ac'), series, { xlabel: `time lag (${unit})`, ylabel: 'direction autocorrelation',
      ymin: Math.min(meta.yMin, Math.floor(Math.min(...lows) * 10) / 10), ymax: meta.yMax + 0.05, title: 'Direction autocorrelation versus time lag' });
  };
  sel.onchange = draw; showTracks.onchange = draw;
  draw();

  const lags = ok[0].lags;
  host.querySelector('#t-sum').innerHTML = `<table><tr><th>lag (${esc(unit)})</th>${ok.map(c => `<th>${esc(c.name)}</th>`).join('')}</tr>
    ${lags.map((l, r) => `<tr><td class="mono">${fmtLag(l)}</td>${ok.map(c => `<td class="mono">${c.avg[r] === null ? '<span class="mute">not computed (n 0)</span>' : `${f3(c.avg[r])} ± ${f3(c.sem[r])} <span class="mute">(n ${c.n_pairs[r]})</span>`}</td>`).join('')}</tr>`).join('')}</table>`;
  const base = meta.file.replace(/\.[^.]+$/, '');
  host.querySelector('#x-sum').onclick = () => download(`${base}_autocorrelation_summary.csv`, summaryCSV(res, meta), 'text/csv');
  host.querySelector('#x-tr').onclick = () => download(`${base}_individual_tracks.csv`, tracksCSV(res, meta), 'text/csv');
}
