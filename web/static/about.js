// About page: what the tool is, the method, how to run the desktop tool and the web app, credits (from the README).
import { route, app, api, esc } from './core.js';

route('about', async () => {
  const info = await api('/info');
  app().innerHTML = `<p class="kicker">About</p><h1>Direction Autocorrelation Analysis</h1>
    <p class="lead">A Python tool for analysing directional persistence in cell migration and particle trajectories from
      fluorescence microscopy data. It was written to process high-density tracks of fluorescently labelled PIEZO1
      proteins, beyond what the original Excel macros could handle.</p>
    <h2>Method</h2>
    <p>Each step between consecutive positions is turned into a unit vector, which keeps the direction and discards the speed.
      For every time lag τ, the scalar products of all pairs of unit vectors τ apart within the same track are pooled;
      the curve is their mean, with the standard error of the mean (sample standard deviation / √n). Lag 0 is 1 by
      definition. Per-track curves are the mean scalar product within each track.</p>
    <p class="eq">C(τ) = ⟨ v̂(t) · v̂(t+τ) ⟩<sub>t</sub></p>
    <p>A value of 1 means straight-line movement, 0 no correlation (random movement), −1 movement in the opposite
      direction; the faster the curve decays, the sooner a cell forgets its direction.</p>
    <p class="small">Reference: <a href="${esc(info.reference.url)}" target="_blank" rel="noopener">${esc(info.reference.text)}</a></p>
    <h2>Run the desktop / command-line tool</h2>
    <pre>pip install -r requirements.txt
python autocorrelation.py 1.0 25 /path/to/file.csv          # one file
python autocorrelation.py 1.0 25 /path/to/condition_folder  # replicates of one condition
python autocorrelation.py 1.0 25 /path/to/experiment_dir    # folders of conditions, compared
python autocorrelation.py                                   # GUI dialogs</pre>
    <p>The command-line tool also aggregates replicate files into condition summaries and compares conditions across an
      experiment directory, writing CSV/Excel tables and PNG plots. The web pages analyse one file at a time.</p>
    <h2>Run the web app</h2>
    <pre>pip install -r requirements-web.txt
python run_web.py        # http://127.0.0.1:8105</pre>
    <p>The local web app sends the file to its own Python server, which runs the repo's <code>core.process_sheet</code>.
      The static GitHub Pages site runs a JavaScript port of the same steps in the browser (<code>dac_engine.js</code>), checked
      against the Python results by a test. The demo data on both is simulated (seeded persistent random walks); the repo
      contains no measured example data.</p>
    <h2>Credits</h2>
    <p>Method: Gorelik &amp; Gautreau (2014). Built with AI assistance from <a href="https://claude.com/" target="_blank" rel="noopener">Claude (Anthropic)</a>.
      Licence: MIT. Source: <a href="https://github.com/gddickinson/${esc(info.repo)}" target="_blank" rel="noopener">github.com/gddickinson/${esc(info.repo)}</a>.</p>`;
});
