// Analyse page: load a CSV (or the simulated demo), set time interval / intervals / pixel size, run the analysis.
// Local app: POST api/analyze runs the repo's Python (core.process_sheet). Static site: static_api.js runs dac_engine.js.
import { route, app, api, esc, isStatic, download } from './core.js';
import { simulateCSV, DEMO } from './dac_sim.js';
import { analyseText, maxDifference } from './dac_engine.js';
import { renderResults } from './analyse_view.js';

// Kept across visits so results survive navigating away and back.
const state = { source: null, result: null, meta: null, settings: null };

function demoSource() {
  const text = simulateCSV();
  return { file: new File([text], 'simulated_demo.csv', { type: 'text/csv' }), text, name: 'simulated_demo.csv', simulated: true };
}

function sourceNote(src) {
  if (!src) return '<span class="mute">No data loaded yet.</span>';
  const lines = src.text ? src.text.split('\n').filter(Boolean).length - 1 : null;
  return src.simulated
    ? `<span class="sim-badge">SIMULATED</span> ${esc(src.name)}: ${DEMO.conditions.length} conditions × ${DEMO.tracks} persistent random walks (seed ${DEMO.seed}), ${lines} rows. Not measured data.`
    : `Loaded <b>${esc(src.name)}</b>${lines !== null ? `: ${lines} rows` : ''}.`;
}

route('analyse', async (args, query) => {
  const info = await api('/info');
  const d = info.defaults;
  const s = state.settings || { dt: d.time_interval, unit: 'min', n: d.num_intervals, coord: 'px', px: '' };
  const engine = isStatic()
    ? 'On this static site the analysis runs <b>in your browser</b> with a JavaScript port of the Python code (tested to agree with it to about 1e-15). Nothing is uploaded.'
    : 'In the local app the analysis runs in <b>Python</b>: the file goes to this computer\'s server, which calls the repo\'s <code>core.process_sheet</code>.';
  app().innerHTML = `<p class="kicker">Analysis</p><h1>Analyse trajectories</h1>
    <p class="lead">Direction autocorrelation of cell or particle tracks: how well the direction of movement at one time
      predicts the direction a given time later.</p>
    <div class="callout a small">${engine}</div>
    <div class="panel"><h3 style="margin-top:0">1 · Data</h3>
      <label for="f-file">Trajectory file (${isStatic() ? 'CSV' : 'CSV or Excel'}; columns frame, x, y and optionally condition. <a href="#/format">Format details</a>)</label>
      <input id="f-file" type="file" accept="${isStatic() ? '.csv,text/csv' : '.csv,.xlsx,.xls'}">
      <button id="b-demo" class="alt" type="button">Use simulated demo data</button>
      <button id="b-demo-dl" class="alt" type="button">Download demo CSV</button>
      <p id="src" class="small">${sourceNote(state.source)}</p></div>
    <div class="panel"><h3 style="margin-top:0">2 · Settings</h3>
      <div class="row">
        <div><label for="s-dt">Time interval between frames</label><input id="s-dt" type="number" min="0" step="any" value="${s.dt}"></div>
        <div><label for="s-unit">Time unit</label><select id="s-unit">${['min', 's', 'ms', 'h', 'frames'].map(u => `<option ${u === s.unit ? 'selected' : ''}>${u}</option>`).join('')}</select></div>
        <div><label for="s-n">Number of intervals (lags)</label><input id="s-n" type="number" min="2" step="1" value="${s.n}"></div>
      </div>
      <div class="row">
        <div><label for="s-coord">x / y coordinates are in</label><select id="s-coord"><option value="px" ${s.coord === 'px' ? 'selected' : ''}>pixels</option><option value="um" ${s.coord === 'um' ? 'selected' : ''}>micrometres (µm)</option></select></div>
        <div><label for="s-px">Pixel size (µm per pixel)</label><input id="s-px" type="number" min="0" step="any" value="${s.px}" placeholder="required for pixel coordinates"></div>
      </div>
      <p class="small mute">The autocorrelation uses unit direction vectors, so it does not depend on the pixel size; the pixel size
        sets the µm axes of the trajectory plot and is recorded in the exported files. The time interval sets the lag axis.
        Defaults come from the repo's <code>config.py</code> (${d.time_interval} per frame, ${d.num_intervals} intervals).</p>
      <button id="b-run" type="button">Analyse</button> <span id="status" class="small" role="status"></span></div>
    <div id="results"></div>`;

  const $ = id => document.getElementById(id);
  const coordSync = () => { $('s-px').disabled = $('s-coord').value === 'um'; };
  $('s-coord').onchange = coordSync; coordSync();
  const setSource = src => { state.source = src; $('src').innerHTML = sourceNote(src); };

  $('f-file').onchange = async e => {
    const f = e.target.files[0];
    if (!f) return;
    const isCsv = /\.csv$/i.test(f.name);
    setSource({ file: f, text: isCsv ? await f.text() : null, name: f.name, simulated: false });
  };
  $('b-demo').onclick = () => {
    setSource(demoSource());
    if (!$('s-px').value) { $('s-px').value = 0.65; $('s-coord').value = 'px'; coordSync(); }
    $('status').textContent = 'Demo loaded with an example pixel size of 0.65 µm/px (change it if you like). Press Analyse.';
  };
  $('b-demo-dl').onclick = () => download('simulated_demo.csv', simulateCSV(), 'text/csv');

  async function run() {
    const dt = +$('s-dt').value, n = +$('s-n').value, coord = $('s-coord').value, px = +$('s-px').value;
    const status = $('status');
    if (!state.source) { status.innerHTML = '<span class="err">Load a file or the simulated demo first.</span>'; return; }
    if (!(dt > 0)) { status.innerHTML = '<span class="err">The time interval must be a positive number.</span>'; return; }
    if (!Number.isInteger(n) || n < 2) { status.innerHTML = '<span class="err">The number of intervals must be a whole number of at least 2.</span>'; return; }
    if (coord === 'px' && !(px > 0)) { status.innerHTML = '<span class="err">Enter the pixel size in µm/px (or choose micrometre coordinates). It is never assumed.</span>'; return; }
    state.settings = { dt, unit: $('s-unit').value, n, coord, px: coord === 'px' ? px : '' };
    const fd = new FormData();
    fd.append('file', state.source.file, state.source.name);
    fd.append('time_interval', String(dt));
    fd.append('num_intervals', String(n));
    $('b-run').disabled = true; status.textContent = 'Analysing...';
    try {
      const res = await api('/analyze', { body: fd });
      let check = null;
      if (res.engine === 'python' && state.source.text) {
        try { check = maxDifference(res, analyseText(state.source.text, dt, n, state.source.name)); } catch { check = null; }
      }
      state.result = res;
      state.meta = { file: state.source.name, simulated: state.source.simulated, timeUnit: state.settings.unit,
        coordUnit: coord, pixelSize: coord === 'px' ? px : 1, check, maxTracks: d.max_tracks_to_plot, yMin: d.plot_y_min, yMax: d.plot_y_max };
      status.textContent = `Done (${res.engine === 'python' ? 'Python' : 'in-browser JS'}).`;
      renderResults($('results'), state.result, state.meta);
    } catch (e) {
      status.innerHTML = `<span class="err">${esc(e.message)}</span>`;
    } finally { $('b-run').disabled = false; }
  }
  $('b-run').onclick = run;

  if ((args[0] === 'demo' || query.demo) && !state.result) {
    setSource(demoSource());
    if (!$('s-px').value) { $('s-px').value = 0.65; $('s-coord').value = 'px'; coordSync(); }
    await run();
  } else if (state.result) renderResults($('results'), state.result, state.meta);
});
