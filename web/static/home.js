// Home page: hero, facts from the repo, and links to the pages.
import { route, app, api, esc, isStatic } from './core.js';

route('home', async () => {
  const info = await api('/info');
  const d = info.defaults;
  app().innerHTML = `<section class="hero"><p class="kicker">Cell migration · particle tracking</p>
    <h1 class="glow">Direction autocorrelation</h1>
    <p class="lead">${esc(info.description)} Load a CSV of trajectories, set the frame interval, and get the
      autocorrelation curve with error bars, a summary table and CSV exports.</p>
    <a class="btn" href="#/analyse/demo">Try it on simulated data</a><a class="btn alt" href="#/analyse">Analyse your file</a></section>
    <div class="tiles">
      <div class="tile"><b>${d.num_intervals}</b><span>time lags by default (config.py)</span></div>
      <div class="tile"><b>${d.time_interval}</b><span>default frame interval (min)</span></div>
      <div class="tile"><b>${info.columns.frame.length + info.columns.x.length + info.columns.y.length}</b><span>accepted frame/x/y column names</span></div>
      <div class="tile"><b>${isStatic() ? 'JS' : 'Python'}</b><span>engine on this ${isStatic() ? 'site' : 'app'}</span></div></div>
    <div class="callout small">C(τ) = ⟨ v̂(t) · v̂(t+τ) ⟩: the scalar product of unit direction vectors τ apart, averaged over all
      pairs. 1 means the same direction, 0 means no memory of the earlier direction, −1 means the opposite direction.</div>
    <div class="grid">
      <a class="card" href="#/analyse"><b>Analyse</b><span>Upload trajectories or use the simulated demo: trajectory map, autocorrelation curve ± SEM, per-track curves, summary table, CSV export.</span></a>
      <a class="card" href="#/format"><b>Data format</b><span>Which columns the tool reads, how trajectories and conditions are recognised, and a demo file to download.</span></a>
      <a class="card" href="#/about"><b>About</b><span>The method (Gorelik &amp; Gautreau 2014), how to run the desktop tool and this web app.</span></a>
    </div>`;
});
