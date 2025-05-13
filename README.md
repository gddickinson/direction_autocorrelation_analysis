# Autocorrelation Analysis

A Python tool for analyzing directional persistence in cell migration and particle trajectories from fluorescence microscopy data.

## Overview

This script performs autocorrelation analysis on trajectory data for fluorescently labeled proteins and cells tracked in microscope recordings. It calculates direction autocorrelation coefficients that quantify how well a cell maintains its direction of movement over time.

Key features:
- Processes individual files or entire experimental datasets
- Supports hierarchical data organization (file → condition → cross-condition analysis)
- Creates detailed visualizations of persistence measurements
- Analyzes individual tracks and condition-level aggregates
- Compares different experimental conditions
- Supports both Excel (.xlsx, .xls) and CSV (.csv) files

## Installation

### Requirements
- Python 3.6 or higher
- Required packages: numpy, pandas, matplotlib, tkinter

```bash
pip install numpy pandas matplotlib
```

## Data Requirements

The script works with cell trajectory data in CSV or Excel format with:
- Frame numbers (time points)
- X coordinates
- Y coordinates

You can organize your data in different ways:
1. **Single file** with one or more sheets (conditions)
2. **Condition folder** containing multiple files (replicates)
3. **Experiment directory** containing multiple condition folders

## Usage

### From Spyder/IDE
Modify the CONFIG section at the top of the script:

```python
# Basic parameters
INPUT_TIME_INTERVAL = 1.0    # Time between frames
INPUT_NUM_INTERVALS = 25     # Number of time intervals to analyze

# Choose ONE of these input modes:
INPUT_FILE = '/path/to/file.csv'  # Single file mode
# or
INPUT_CONDITION_DIR = '/path/to/condition_folder'  # Condition folder mode
# or
INPUT_EXPERIMENT_DIR = '/path/to/experiment_dir'   # Experiment directory mode

# Advanced options
SAVE_INDIVIDUAL_TRACKS = True  # Save track-by-track data
PLOT_INDIVIDUAL_TRACKS = True  # Create plots with individual tracks
MAX_TRACKS_TO_PLOT = 100       # Maximum number of tracks to show
PLOT_Y_MIN = -0.2              # Y-axis minimum value
PLOT_Y_MAX = 1.0               # Y-axis maximum value
```

### From Command Line

```bash
# Single file mode
python autocorrelation.py 1.0 25 /path/to/file.csv

# Condition folder mode
python autocorrelation.py 1.0 25 /path/to/condition_folder

# Experiment directory mode
python autocorrelation.py 1.0 25 /path/to/experiment_dir
```

Where:
- First parameter: Time interval between frames
- Second parameter: Number of intervals to analyze
- Third parameter: Path to file or directory
- Optional fourth parameter: File pattern (e.g., "*.csv;*.xlsx")

### With GUI

Run the script without parameters to use the GUI mode:

```bash
python autocorrelation.py
```

The GUI will prompt you for:
1. Time interval and number of intervals
2. Analysis mode (single file, condition folder, or experiment directory)
3. File or directory selection

## Output Structure

### For Single Files
- `filename_averages.csv/xlsx` - Summary statistics for each sheet/condition
- `filename_individual_tracks.csv/xlsx` - Per-track analysis data
- `filename_autocorrelation_plot.png` - Direction autocorrelation plot
- `filename_individual_tracks_plot.png` - Individual tracks visualization

### For Condition Folders
- Individual file outputs (as above)
- `condition_summary.csv/xlsx` - Statistics aggregated across all files
- `condition_summary_plot.png` - Condition-level autocorrelation plot
- `condition_all_tracks_plot.png` - All individual tracks in the condition

### For Experiment Directories
- Condition-level outputs (as above) in each condition folder
- `condition_comparison_plot.png` - Cross-condition comparison
- `all_conditions_summary.csv/xlsx` - Summary statistics across conditions

## Understanding Direction Autocorrelation

Direction autocorrelation measures how well a cell maintains its direction over time. It calculates the correlation between movement vectors at different time intervals:
- Value of 1.0: Perfect correlation (straight-line movement)
- Value of 0.0: No correlation (random movement)
- Value of -1.0: Anti-correlation (movement in opposite direction)

The decay rate of the autocorrelation curve indicates how quickly a cell's movement becomes uncorrelated with its initial direction.

## Hierarchical Data Organization

For optimal analysis of experimental data with multiple conditions, organize your files as:

```
experiment_directory/
├── control/
│   ├── experiment1.csv
│   ├── experiment2.csv
│   └── ...
├── treatment1/
│   ├── experiment1.csv
│   └── ...
└── treatment2/
    ├── experiment1.csv
    └── ...
```

This allows automatic cross-condition comparison and aggregate statistics.

## Tips

1. **Frame Rate Selection**: Choose an appropriate time interval between frames. Too short intervals may capture noise; too long may miss important cell movements.

2. **Number of Intervals**: Set based on how long you want to track directional persistence. Higher values analyze longer-term behavior.

3. **Y-Axis Scale**: Default is set to -0.2 to 1.0 for consistent visualization across conditions.

4. **Track Visualization**: For datasets with many tracks, `MAX_TRACKS_TO_PLOT` limits the number displayed to maintain clarity.

5. **Output Format**: Results are saved in the same format as input files (CSV for CSV input, Excel for Excel input).

## Reference

This script implements directional persistence analysis as described in:
Gorelik, R., & Gautreau, A. (2014). Quantitative and unbiased analysis of directional persistence in cell migration. *Nature Protocols, 9*(8), 1931-1943.
