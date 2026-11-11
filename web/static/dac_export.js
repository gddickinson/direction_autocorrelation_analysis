// CSV exports of an analysis result. Each file starts with '#' comment lines recording the settings and units, so the
// numbers stay traceable (read back with pandas.read_csv(path, comment='#')).

const q = v => (/[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
const n = v => (v === null || v === undefined ? '' : String(v));

export function header(res, meta) {
  return [
    `# direction autocorrelation results (engine: ${res.engine === 'python' ? 'Python core.process_sheet' : 'JS port dac_engine.js'})`,
    `# source file: ${meta.file}${meta.simulated ? ' (SIMULATED demo data, not measurements)' : ''}`,
    `# time_interval: ${res.time_interval} ${meta.timeUnit} per frame; num_intervals: ${res.num_intervals}`,
    `# coordinates: ${meta.coordUnit === 'px' ? `pixels, pixel size ${meta.pixelSize} um/px (used for the trajectory plot only)` : 'micrometres'}`,
    '# direction autocorrelation is dimensionless (unit vectors): pixel size does not change AVG or SEM',
  ];
}

// Long format: one row per condition and lag (AVG, SEM, number of scalar products).
export function summaryCSV(res, meta) {
  const lines = header(res, meta);
  lines.push(`condition,time_lag_${meta.timeUnit},AVG,SEM,n_scalar_products`);
  for (const c of res.conditions) {
    if (c.error) continue;
    c.lags.forEach((t, i) => lines.push([q(c.name), t, n(c.avg[i]), n(c.sem[i]), c.n_pairs[i]].join(',')));
  }
  return lines.join('\n') + '\n';
}

// Per-track mean correlations, as save_individual_track_results writes them, plus a condition column.
export function tracksCSV(res, meta) {
  const lines = header(res, meta);
  lines.push('condition,track_id,time_interval,correlation');
  for (const c of res.conditions) {
    if (c.error) continue;
    for (const t of c.tracks) t.t.forEach((v, i) => lines.push([q(c.name), t.id, v, n(t.c[i])].join(',')));
  }
  return lines.join('\n') + '\n';
}
