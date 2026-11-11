# Session log

## 2026-11-11 — web interface and static site (branch `web-interface`)
- Added `web/` (FastAPI app on port 8105, `run_web.py`) and a static GitHub Pages build (`scripts/build_static.py`,
  `.github/workflows/pages.yml`) from the shared web kit. Pages: Home, Analyse, Data format, About.
- Local app: `POST /api/analyze` runs the repo's own `io_utils.read_file` + `core.process_sheet` (`web/analysis.py`).
- Static site: `web/static/dac_engine.js` ports identify_columns + process_sheet to JS. Agreement with Python on the
  fixture (3 cases: 4 conditions, edge cases incl. a 1-point track, zero step, missing value, frame gap, alias headers,
  6-column fallback): worst |JS - Python| = 4.4e-16; on the 1821-row demo, 8.9e-16 (in-page cross-check).
- Fixed in core.py (George approved): `calculate_normed_vectors` took track starts from index labels but sliced with
  iloc, so in the CLI every condition after the first in a multi-condition CSV was NaN and dropped NaN rows could shift
  track boundaries. Now positional starts + `reset_index` in `process_sheet`; results for single-condition files
  unchanged; regression tests `TestIndexLabelsIndependence` in test_core.py. Also by design of core.py the last lag
  (num_intervals * dt) is never computed (AVG NaN, SEM 0); the web reproduces and labels this.
- Demo data are simulated (the repo has no generator or example data): seeded persistent random walks, labelled
  SIMULATED everywhere, with the theoretical curve overlaid.
- Pixel size is required for pixel coordinates (never assumed); it only scales the trajectory plot and is recorded in
  exports, since the autocorrelation uses unit vectors.
- Tests: tests/test_web.py 13 passed; test_core.py 16 passed; node dac_engine test ok; screenshots static + local ok.
