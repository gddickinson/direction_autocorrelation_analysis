"""
Enhanced Hierarchical Autocorrelation Analysis

This script performs autocorrelation analysis on trajectory data organized in a
hierarchical folder structure representing different experimental conditions.

Features:
- Processes hierarchical folder structures (condition folders containing multiple files)
- Calculates individual file statistics
- Aggregates results across all files in a condition
- Creates condition-level summaries showing mean and SEM across experiments
- Creates cross-condition comparisons and visualization
- Supports both Excel (.xlsx, .xls) and CSV (.csv) files
- Exports individual track results for detailed analysis
- Plots individual tracks alongside average results

This file is a backward-compatible entry point. The actual implementation has been
split into separate modules for maintainability:
    - config.py    -- Configuration parameters
    - core.py      -- Autocorrelation math (vector normalization, scalar products)
    - io_utils.py  -- File reading/writing
    - plotting.py  -- Visualization
    - cli.py       -- CLI/GUI entry points and orchestration
"""

# Re-export everything so existing imports/usage still works
from config import (  # noqa: F401
    INPUT_TIME_INTERVAL, INPUT_NUM_INTERVALS,
    INPUT_FILE, INPUT_CONDITION_DIR, INPUT_EXPERIMENT_DIR,
    FILE_PATTERN, OUTPUT_DIR,
    SAVE_INDIVIDUAL_TRACKS, PLOT_INDIVIDUAL_TRACKS, MAX_TRACKS_TO_PLOT,
    PLOT_Y_MIN, PLOT_Y_MAX,
)

from core import (  # noqa: F401
    calculate_normed_vectors,
    calculate_scalar_products,
    calculate_averages,
    process_sheet,
    aggregate_condition_results,
)

from io_utils import (  # noqa: F401
    get_file_type,
    read_file,
    identify_columns,
    expand_file_patterns,
    save_averages,
    save_individual_track_results,
    save_stats,
    save_condition_individual_tracks,
    create_condition_summary,
    create_cross_condition_summary,
)

from plotting import (  # noqa: F401
    create_autocorrel_plot,
    plot_individual_tracks,
    create_condition_plot,
    create_condition_individual_tracks_plot,
    create_cross_condition_plot,
)

from cli import (  # noqa: F401
    get_user_inputs,
    process_file,
    process_condition_folder,
    process_experiment_directory,
    run_analysis,
    main,
)


if __name__ == "__main__":
    main()
