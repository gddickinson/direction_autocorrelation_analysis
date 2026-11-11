// Small SVG plotting helpers (no libraries): line plots with error bars, and trajectory maps with equal axes.
import { esc } from './core.js';

export const COLORS = ['#36e2ff', '#ffb43f', '#b18cff', '#ff5c7a', '#3dff8f', '#ff8a3d', '#5aa9ff', '#f2f26b'];
const W = 640, H = 380, M = { l: 58, r: 16, t: 16, b: 46 };

export function niceTicks(lo, hi, n = 6) {
  if (!(hi > lo)) { hi = lo + 1; }
  const raw = (hi - lo) / n, p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(m => m * p).find(s => s >= raw);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12));
  return out;
}
const fmtTick = v => (Math.abs(v) >= 1e4 || (Math.abs(v) < 1e-3 && v !== 0) ? v.toExponential(1) : String(+v.toPrecision(4)));

function frame(xs, ys, sx, sy, { xlabel, ylabel }) {
  let g = '';
  for (const v of ys) g += `<line x1="${M.l}" x2="${W - M.r}" y1="${sy(v)}" y2="${sy(v)}" class="grid-l"/><text x="${M.l - 8}" y="${sy(v) + 4}" text-anchor="end">${fmtTick(v)}</text>`;
  for (const v of xs) g += `<line y1="${M.t}" y2="${H - M.b}" x1="${sx(v)}" x2="${sx(v)}" class="grid-l"/><text x="${sx(v)}" y="${H - M.b + 18}" text-anchor="middle">${fmtTick(v)}</text>`;
  g += `<rect x="${M.l}" y="${M.t}" width="${W - M.l - M.r}" height="${H - M.t - M.b}" class="axis-box"/>`;
  g += `<text x="${(M.l + W - M.r) / 2}" y="${H - 8}" text-anchor="middle" class="axis-label">${esc(xlabel)}</text>`;
  g += `<text transform="translate(15 ${(M.t + H - M.b) / 2}) rotate(-90)" text-anchor="middle" class="axis-label">${esc(ylabel)}</text>`;
  return g;
}

function legend(items) {
  if (!items.length) return '';
  return `<div class="legend">${items.map(s => `<span><i style="background:${s.color}${s.dash ? ';opacity:.6' : ''}"></i>${esc(s.label)}</span>`).join('')}</div>`;
}

// series: [{x, y, err?, color, label?, dash?, width?, opacity?, dots?}]; null y values break the line.
export function linePlot(el, series, { xlabel = '', ylabel = '', ymin, ymax, xmin = 0, title = 'plot' } = {}) {
  const all = series.flatMap(s => s.x.map((x, i) => [x, s.y[i], s.err ? s.err[i] : 0])).filter(p => p[1] !== null && Number.isFinite(p[1]));
  const xmax = Math.max(xmin + 1e-9, ...all.map(p => p[0]));
  const lo = ymin ?? Math.min(...all.map(p => p[1] - (p[2] || 0))), hi = ymax ?? Math.max(...all.map(p => p[1] + (p[2] || 0)));
  const sx = v => M.l + (v - xmin) / (xmax - xmin) * (W - M.l - M.r);
  const sy = v => H - M.b - (v - lo) / (hi - lo || 1) * (H - M.t - M.b);
  const clampY = v => Math.max(M.t, Math.min(H - M.b, sy(v)));
  let body = '';
  for (const s of series) {
    let d = '', pen = false;
    s.x.forEach((x, i) => {
      const y = s.y[i];
      if (y === null || !Number.isFinite(y)) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${sx(x).toFixed(1)},${clampY(y).toFixed(1)}`; pen = true;
    });
    const op = s.opacity ?? 1;
    body += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.width ?? 2}" stroke-opacity="${op}"${s.dash ? ` stroke-dasharray="${s.dash}"` : ''}/>`;
    if (s.err) s.x.forEach((x, i) => {
      const y = s.y[i], e = s.err[i];
      if (y === null || e === null || !Number.isFinite(y) || !(e > 0)) return;
      const X = sx(x).toFixed(1);
      body += `<path d="M${X},${clampY(y - e).toFixed(1)}V${clampY(y + e).toFixed(1)}M${(+X - 4)},${clampY(y - e).toFixed(1)}h8M${(+X - 4)},${clampY(y + e).toFixed(1)}h8" stroke="${s.color}" stroke-width="1.4"/>`;
    });
    if (s.dots) s.x.forEach((x, i) => { const y = s.y[i]; if (y !== null && Number.isFinite(y)) body += `<circle cx="${sx(x).toFixed(1)}" cy="${clampY(y).toFixed(1)}" r="3" fill="${s.color}"/>`; });
  }
  const zero = lo < 0 && hi > 0 ? `<line x1="${M.l}" x2="${W - M.r}" y1="${sy(0)}" y2="${sy(0)}" class="zero-l"/>` : '';
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" class="plot" role="img" aria-label="${esc(title)}">${frame(niceTicks(xmin, xmax), niceTicks(lo, hi), sx, sy, { xlabel, ylabel })}${zero}${body}</svg>${legend(series.filter(s => s.label))}`;
}

// Trajectory map. segments: [{x, y}] in data units (already scaled); y increases downwards (image coordinates).
export function trajectoryPlot(el, segments, { unit = 'µm', title = 'trajectories', color = COLORS[0] } = {}) {
  const xs = segments.flatMap(s => s.x), ys = segments.flatMap(s => s.y);
  if (!xs.length) { el.innerHTML = '<p class="mute">No trajectories to draw.</p>'; return; }
  let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const span = Math.max(x1 - x0, y1 - y0) || 1, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  x0 = cx - span * 0.55; x1 = cx + span * 0.55; y0 = cy - span * 0.55; y1 = cy + span * 0.55;
  const S = 460, m = { l: 58, t: 12, b: 46, r: 12 };
  const sx = v => m.l + (v - x0) / (x1 - x0) * (S - m.l - m.r), sy = v => m.t + (v - y0) / (y1 - y0) * (S - m.t - m.b);
  let g = '';
  for (const v of niceTicks(x0, x1, 5)) g += `<line y1="${m.t}" y2="${S - m.b}" x1="${sx(v)}" x2="${sx(v)}" class="grid-l"/><text x="${sx(v)}" y="${S - m.b + 18}" text-anchor="middle">${fmtTick(v)}</text>`;
  for (const v of niceTicks(y0, y1, 5)) g += `<line x1="${m.l}" x2="${S - m.r}" y1="${sy(v)}" y2="${sy(v)}" class="grid-l"/><text x="${m.l - 8}" y="${sy(v) + 4}" text-anchor="end">${fmtTick(v)}</text>`;
  g += `<rect x="${m.l}" y="${m.t}" width="${S - m.l - m.r}" height="${S - m.t - m.b}" class="axis-box"/>`;
  g += `<text x="${(m.l + S - m.r) / 2}" y="${S - 8}" text-anchor="middle" class="axis-label">x (${esc(unit)})</text>`;
  g += `<text transform="translate(15 ${(m.t + S - m.b) / 2}) rotate(-90)" text-anchor="middle" class="axis-label">y (${esc(unit)}, downwards)</text>`;
  segments.forEach((s, i) => {
    if (s.x.length < 1) return;
    const d = s.x.map((x, k) => `${k ? 'L' : 'M'}${sx(x).toFixed(1)},${sy(s.y[k]).toFixed(1)}`).join('');
    const c = Array.isArray(color) ? color[i % color.length] : color;
    g += `<path d="${d}" fill="none" stroke="${c}" stroke-width="1.3" stroke-opacity=".85"/><circle cx="${sx(s.x[0]).toFixed(1)}" cy="${sy(s.y[0]).toFixed(1)}" r="2.2" fill="${c}"/>`;
  });
  el.innerHTML = `<svg viewBox="0 0 ${S} ${S}" class="plot square" role="img" aria-label="${esc(title)}">${g}</svg>`;
}
