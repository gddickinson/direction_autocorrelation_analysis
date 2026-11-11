// SIMULATED demo trajectories (the repo has no data generator, so this is not real data).
// Persistent random walk, the same model test_core.py uses: the heading changes by a Gaussian turn N(0, sigma) radians
// every frame and each step has a fixed length. For this model the expected direction autocorrelation at a lag of m
// frames is exp(-m sigma^2 / 2), which the analysis page overlays as a check.
// Output is CSV text in the format the tool reads: condition, track_id, frame, x, y (x/y in pixels).
import { rng } from './core.js';

export const DEMO = {
  seed: 2014, tracks: 20, minLen: 25, maxLen: 70, step: 3, field: 512,
  conditions: [{ name: 'persistent (sigma 0.3 rad)', sigma: 0.3 }, { name: 'less persistent (sigma 0.9 rad)', sigma: 0.9 }],
};

function normal(r) {
  let u = 0;
  while (u === 0) u = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
}

export function simulateCSV(opts = {}) {
  const o = { ...DEMO, ...opts }, r = rng(o.seed);
  const lines = ['condition,track_id,frame,x,y'];
  let id = 0;
  for (const c of o.conditions) {
    for (let t = 0; t < o.tracks; t++) {
      id++;
      const len = o.minLen + Math.floor(r() * (o.maxLen - o.minLen + 1));
      let x = o.field * (0.15 + 0.7 * r()), y = o.field * (0.15 + 0.7 * r()), th = 2 * Math.PI * r();
      for (let f = 1; f <= len; f++) {
        lines.push(`${c.name},${id},${f},${x.toFixed(3)},${y.toFixed(3)}`);
        x += o.step * Math.cos(th); y += o.step * Math.sin(th);
        th += c.sigma * normal(r);
      }
    }
  }
  return lines.join('\n') + '\n';
}

// Expected C(lag) for the simulated model; steps are lags in frames.
export function theoryCurve(sigma, steps) { return steps.map(m => Math.exp(-m * sigma * sigma / 2)); }
