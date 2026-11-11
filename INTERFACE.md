# Direction Autocorrelation Analysis — Interface Map

## Module Structure

### Entry Points
- **autocorrelation.py** — Backward-compatible wrapper that re-exports everything from the split modules. Run with `python autocorrelation.py` or import individual functions.
- **cli.py** — CLI and GUI entry points, orchestration logic
  - `main()` — Dispatches to config/CLI/GUI mode
  - `run_analysis(...)` — Programmatic entry point
  - `process_file(input_file, time_interval, num_intervals, output_dir, ...)` -> (success, results, error)
  - `process_condition_folder(input_dir, file_pattern, ...)` -> (success_count, fail_count, results, summary)
  - `process_experiment_directory(input_dir, file_pattern, ...)` -> (success_count, fail_count, summaries)
  - `get_user_inputs()` -> (time_interval, num_intervals) via tkinter dialogs

### Core Computation
- **core.py** — Autocorrelation math engine
  - `calculate_normed_vectors(df)` -> (result_df, traj_starts)
  - `calculate_scalar_products(df, traj_starts, time_interval, num_intervals)` -> (combined_df, tracks_df)
  - `calculate_averages(scalar_products)` -> DataFrame with AVG/SEM rows
  - `process_sheet(sheet_df, time_interval, num_intervals)` -> (scalar_products, averages, tracks)
  - `aggregate_condition_results(results_list, condition_name)` -> (summary_df, file_type, tracks_df); one replicate per sheet (file:sheet for multi-sheet files)

### I/O
- **io_utils.py** — File reading/writing
  - `read_file(file_path)` -> (data_source, file_type)
  - `identify_columns(df)` -> DataFrame with frame/x/y columns
  - `save_averages(...)`, `save_stats(...)`, `save_individual_track_results(...)`
  - `create_condition_summary(...)`, `create_cross_condition_summary(...)`

### Visualization
- **plotting.py** — All plot generation
  - `create_autocorrel_plot(all_results, output_dir, ...)`
  - `plot_individual_tracks(tracks_df, averages, output_dir, ...)`
  - `create_condition_plot(summary_df, output_dir, condition_name)`
  - `create_condition_individual_tracks_plot(...)`
  - `create_cross_condition_plot(condition_summaries, main_output_dir)`

### Configuration
- **config.py** — All tunable parameters (time interval, paths, plot settings)

### Web interface (`web/`, local app + static GitHub Pages site)
- **run_web.py** — starts uvicorn on 127.0.0.1:8105 (`web.app:app`)
- **web/app.py** — FastAPI: serves `web/static/`, `GET /api/info` (config defaults, accepted column names, reference),
  `POST /api/analyze` (multipart: file, time_interval, num_intervals). `STATIC_ENDPOINTS` = GETs exported to the static site
- **web/analysis.py** — bridge to the real Python code: `analyse_upload(filename, bytes, dt, n)` -> io_utils.read_file,
  then per sheet `analyse_sheet(...)`: identify_columns, dropna, reset_index, core.process_sheet -> JSON
  (lags, avg, sem, n_pairs, tracks, segments). Explains why the index is reset (row labels vs positions in core.py)
- **web/static/** — ES modules, no build step
  - `core.js`, `style.css` (shared web kit, unchanged); `style_app.css` (accents, plot styles); `index.html`; `icon.svg`
  - `main.js` (lazy page registry, footer mode) · `home.js` · `analyse.js` (inputs, run, Python/JS cross-check) ·
    `analyse_view.js` (tiles, plots, summary table, exports) · `format.js` (data format, demo download) · `about.js`
  - `dac_engine.js` — JS port of read_file (CSV) + identify_columns + process_sheet; `analyseText`, `maxDifference`
  - `dac_engine.test.mjs` — node test: JS vs Python fixture (tol 1e-9) plus core.py conventions
  - `dac_sim.js` — SIMULATED seeded persistent random walks (demo) and the theory curve exp(-m sigma^2/2)
  - `dac_plots.js` — SVG line plot with error bars, trajectory map · `dac_export.js` — summary / per-track CSV
  - `static_api.js` — static site: GET from exported JSON, `/analyze` via dac_engine.js
- **scripts/build_static.py** — exports `site/` (front end + STATIC_ENDPOINTS JSON)
- **scripts/screenshots.py** — Playwright smoke test + README images; **scripts/screenshot_results.py** — results image
- **scripts/make_dac_fixture.py** — writes `tests/fixtures/dac_fixture.json` from the Python analysis
- **.github/workflows/pages.yml** — tests, builds and publishes the static site on push to main
- **requirements-web.txt** — pinned web/test dependencies

### Tests
- **test_core.py** — 23 tests (incl. `TestConditionAggregationSheets`: every sheet a replicate, single-sheet output equals the frozen reference `tests/fixtures/pre_multisheet_reference.json`): vector normalization, scalar products (incl. `TestAllLagsComputed`: last lag computed, earlier lags equal the frozen pre-fix reference `tests/fixtures/pre_lastlag_reference.json`), averaging, index-label independence, column identification, file type detection
- **tests/test_web.py** — web API (fixture agreement, CLI-path identity, all conditions analysed, Excel, bad input),
  static build, and runs the node JS-engine tests

### Documentation
- **analysis_details.md** — Detailed description of the autocorrelation algorithm
- **README.md** — Usage instructions (incl. web interface section; images in `docs/img/`)
- **SESSION_LOG.md** — Session progress log
