# Direction Autocorrelation Analysis — Roadmap

## Current State
A modular Python package for analyzing directional persistence in cell migration trajectories. Supports single-file, condition-folder, and experiment-directory modes with GUI (tkinter dialogs) and CLI interfaces. Produces detailed plots and CSV/Excel output. Well-documented in README and `analysis_details.md`.

## Short-term Improvements
- [x] Split `autocorrelation.py` (1,611 lines) into modules: `core.py` (autocorrelation math), `io_utils.py` (file reading/writing), `plotting.py` (visualization), `cli.py` (argument parsing and GUI), `config.py` (CONFIG parameters)
- [ ] Replace the CONFIG block pattern with argparse + YAML/JSON config file support
- [ ] Add input validation: check for minimum track length, required columns, handle empty sheets gracefully
- [ ] Add type hints to all functions
- [x] Add error messages that identify which file/sheet caused a failure (currently uses bare try/except)
- [x] Add `requirements.txt` with numpy, pandas, matplotlib, openpyxl
- [x] Add unit tests for the core autocorrelation calculation using synthetic data with known persistence

## Feature Enhancements
- [ ] Add exponential decay fitting to extract persistence time from autocorrelation curves
- [ ] Add statistical tests (t-test, Mann-Whitney) for comparing conditions automatically
- [ ] Add support for irregular time intervals (weighted autocorrelation)
- [ ] Add HTML report generation with embedded plots for easier sharing
- [ ] Add progress bars (tqdm) for large datasets instead of print statements
- [ ] Add parallel processing for experiment-directory mode (process conditions concurrently)
- [ ] Add a `--dry-run` flag to preview what files would be processed without running analysis

## Long-term Vision
- [ ] Build a Streamlit or Dash web app for interactive analysis with drag-and-drop file upload
- [ ] Add integration with the `diper_clone` project — share core analysis functions
- [ ] Package as a pip-installable tool: `pip install autocorrelation-analysis`
- [ ] Add support for reading TrackMate XML and Imaris CSV formats directly
- [ ] Add mean squared displacement (MSD) analysis as a companion metric
- [ ] Add animation of cell trajectories alongside autocorrelation decay curves

## Technical Debt
- [x] The 1,611-line monolith violates single-responsibility — splitting is the top priority
- [x] Hardcoded paths in CONFIG block (e.g., `/Users/george/Desktop/...`) should be removed or made relative
- [x] Plotting code is interleaved with computation — separate data generation from rendering
- [ ] Uses `random.sample` for track color selection — should use a deterministic colormap
- [ ] Exception handling is too broad in several places (`except:` with no type)
- [x] No `.gitignore` — output files and data may get committed accidentally
