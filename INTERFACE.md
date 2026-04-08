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
  - `aggregate_condition_results(results_list, condition_name)` -> (summary_df, file_type, tracks_df)

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

### Tests
- **test_core.py** — 16 tests covering vector normalization, scalar products, averaging, column identification, file type detection

### Documentation
- **analysis_details.md** — Detailed description of the autocorrelation algorithm
- **README.md** — Usage instructions
