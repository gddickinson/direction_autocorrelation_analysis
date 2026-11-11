// Data format page: what io_utils.read_file / identify_columns accept, with an example and the demo download.
import { route, app, api, esc, isStatic, download } from './core.js';
import { simulateCSV } from './dac_sim.js';

const code = a => a.map(c => `<code>${esc(c)}</code>`).join(' ');

route('format', async () => {
  const info = await api('/info');
  const c = info.columns;
  app().innerHTML = `<p class="kicker">Input</p><h1>Data format</h1>
    <p class="lead">One table of positions, one row per frame of each track, tracks one after another. CSV works everywhere;
      Excel (.xlsx/.xls, one condition per sheet) works in the local app${isStatic() ? ' only' : ''}.</p>
    <div class="panel"><h3 style="margin-top:0">Columns</h3>
      <table><tr><th>Role</th><th>Accepted header names (any case)</th></tr>
        <tr><td>frame</td><td>${code(c.frame)}</td></tr>
        <tr><td>x</td><td>${code(c.x)}</td></tr>
        <tr><td>y</td><td>${code(c.y)}</td></tr>
        <tr><td>condition (optional)</td><td>${code(c.condition)}: each value becomes a separate condition, analysed and plotted separately</td></tr></table>
      <p class="small">If the names are not found and the table has at least 6 columns, the 4th, 5th and 6th columns are used as
        frame, x and y (the original Excel-macro layout). Other columns (track ID, intensity...) are ignored.</p></div>
    <div class="panel"><h3 style="margin-top:0">How tracks are recognised</h3>
      <p>There is no track-ID column in the analysis: <b>a new track starts wherever the frame number does not increase</b>
        from one row to the next. So sort rows by track, then by frame, and start each track at a frame number lower than
        or equal to the previous row's. Gaps in frame numbers within a track are not filled in: consecutive rows are treated
        as consecutive steps.</p>
      <p>Rows with a missing frame, x or y are dropped. Steps of zero length have no direction and are skipped.</p></div>
    <div class="panel"><h3 style="margin-top:0">Units</h3>
      <p>x and y can be in pixels or micrometres. The autocorrelation uses unit direction vectors, so it does not depend on
        the scale; the pixel size you enter (µm per pixel) is used for the trajectory plot axes and recorded in exports.
        The time lag axis is the frame index × the time interval you enter.</p></div>
    <h2>Example</h2>
    <pre>condition,track_id,frame,x,y
control,1,1,212.40,180.02
control,1,2,214.97,181.33
control,1,3,217.10,183.05
control,2,1,64.81,300.55      &lt;- frame drops: a new track
control,2,2,63.02,302.90
treated,3,1,401.77,95.20</pre>
    <p><button id="dl" type="button">Download demo CSV</button>
      <span class="small mute">Simulated persistent random walks (seeded), in exactly this layout. Not measured data.</span></p>`;
  document.getElementById('dl').onclick = () => download('simulated_demo.csv', simulateCSV(), 'text/csv');
});
