"""
Configuration parameters for autocorrelation analysis.

These can be overridden by command-line arguments or GUI inputs.
Set values to None to use interactive/CLI mode instead.
"""

# Time between frames (minutes)
INPUT_TIME_INTERVAL = 1.0

# Number of time intervals to analyze
INPUT_NUM_INTERVALS = 25

# Experiment directory containing condition folders
# Set to None to use GUI or CLI
# INPUT_EXPERIMENT_DIR = '/path/to/experiment'
INPUT_EXPERIMENT_DIR = None

# Single condition folder
# Set to None to use experiment directory mode or single file mode
INPUT_CONDITION_DIR = None

# Single file mode
# Set to None to use condition or experiment mode
INPUT_FILE = None

# File pattern to match (semicolon-separated)
FILE_PATTERN = "*.xlsx;*.xls;*.csv"

# Output directory (created if it doesn't exist)
OUTPUT_DIR = "autocorrelation_output"

# Advanced options
SAVE_INDIVIDUAL_TRACKS = True
PLOT_INDIVIDUAL_TRACKS = True
MAX_TRACKS_TO_PLOT = 100
PLOT_Y_MIN = -0.2
PLOT_Y_MAX = 1.0
