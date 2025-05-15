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
"""

import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tkinter import simpledialog, Tk, messagebox, filedialog
import math
import sys
import time
import re
from collections import defaultdict
import traceback
import random

#############################################################
# CONFIG - Modify these parameters for direct execution in IDE
#############################################################
# Set to None to use command-line args or GUI
INPUT_TIME_INTERVAL = 200.0  # Time between frames
INPUT_NUM_INTERVALS = 25    # Number of time intervals to analyze

# Experiment directory containing condition folders
#INPUT_EXPERIMENT_DIR = None  # e.g., "/path/to/experiment"
INPUT_EXPERIMENT_DIR ='/Users/george/Desktop/gabby_10ms_data_bin20/linearity/GoF_Yoda1/results/mobile_results'

# Single condition folder - Set to None to use experiment directory mode
INPUT_CONDITION_DIR = None  # e.g., "/path/to/control"

# Single file mode - Set to None to use condition or experiment mode
INPUT_FILE = None
#INPUT_FILE = '/Users/george/Desktop/diPer/41596_2014_BFnprot2014131_MOESM398_ESM.xlsx' # e.g., "/path/to/file.csv"

# File pattern to match
FILE_PATTERN = "*.xlsx;*.xls;*.csv"  # Semicolon-separated

# Output directory (created if it doesn't exist)
OUTPUT_DIR = "autocorrelation_output"

# Plot options
SAVE_INDIVIDUAL_TRACKS = True  # Save individual track data to files
PLOT_INDIVIDUAL_TRACKS = True  # Create plots with individual tracks
MAX_TRACKS_TO_PLOT = 100      # Maximum number of tracks to show in individual track plots
PLOT_Y_MIN = -0.2             # Minimum y-axis value for all plots
PLOT_Y_MAX = 1.0              # Maximum y-axis value for all plots
PLOT_X_MIN = 0                # Minimum x-axis value for all plots
PLOT_X_MAX = 2000            # Maximum x-axis value for all plots (None for auto-scaling based on data)

# Cross-condition plot options
CROSS_CONDITION_PLOT_TITLE = 'GOF-YODA1'  # Custom title for cross-condition plot (None = use default "Comparison Across Conditions")
#############################################################


def get_user_inputs():
    """Get time interval and number of intervals from the user via GUI."""
    root = Tk()
    root.withdraw()  # Hide the main window

    time_interval = simpledialog.askfloat(
        "Time Interval",
        "Enter a positive number (minutes)\nWhat is the time interval between frames?",
        parent=root
    )

    if time_interval is None or time_interval <= 0:
        root.destroy()
        return None, None

    num_intervals = simpledialog.askinteger(
        "Number of Intervals",
        "Enter a positive integer only\nPlease enter the number of time intervals",
        parent=root
    )

    if num_intervals is None or num_intervals <= 0:
        root.destroy()
        return None, None

    root.destroy()
    return time_interval, num_intervals


def get_file_type(file_path):
    """
    Determine the file type based on extension.

    Args:
        file_path (str): Path to the file

    Returns:
        str: 'excel' or 'csv'
    """
    _, ext = os.path.splitext(file_path.lower())
    if ext in ['.xlsx', '.xls']:
        return 'excel'
    elif ext == '.csv':
        return 'csv'
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def read_file(file_path):
    """
    Read a file based on its extension.

    Args:
        file_path (str): Path to the file

    Returns:
        tuple: (pandas.ExcelFile or list of DataFrames, file_type)
    """
    file_type = get_file_type(file_path)

    if file_type == 'excel':
        # Read Excel file
        excel_file = pd.ExcelFile(file_path)
        return excel_file, file_type

    elif file_type == 'csv':
        # Read CSV file
        try:
            # First try with default settings
            df = pd.read_csv(file_path)

            # Check if we need to handle sheets differently
            # If there's a column that might indicate a 'sheet' or 'condition'
            potential_sheet_cols = ['sheet', 'condition', 'group', 'experiment']

            sheet_col = None
            for col in potential_sheet_cols:
                if col in df.columns or col.lower() in [c.lower() for c in df.columns]:
                    # Find the actual column name (case insensitive)
                    sheet_col = next(c for c in df.columns if c.lower() == col.lower())
                    break

            if sheet_col:
                # Split the dataframe by the sheet column
                sheet_groups = df.groupby(sheet_col)
                sheets = {name: group.drop(sheet_col, axis=1) for name, group in sheet_groups}
            else:
                # Treat the whole CSV as a single sheet
                sheets = {'Sheet1': df}

            return sheets, file_type

        except Exception as e:
            print(f"Error reading CSV file: {str(e)}")
            # Try with different encoding
            try:
                df = pd.read_csv(file_path, encoding='latin1')
                sheets = {'Sheet1': df}
                return sheets, file_type
            except Exception as e2:
                raise ValueError(f"Failed to read CSV file: {str(e2)}")

    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def identify_columns(df):
    """
    Identify 'frame', 'x', 'y' columns in the dataframe regardless of their position.

    Args:
        df (pandas.DataFrame): Input dataframe

    Returns:
        pandas.DataFrame: DataFrame with only 'frame', 'x', 'y' columns,
                         or None if the required columns are not found
    """
    # Create a lowercase mapping of column names
    cols_lower = {col.lower(): col for col in df.columns}

    # Look for variations of column names
    frame_col = None
    x_col = None
    y_col = None

    # Frame column variations
    frame_options = ['frame', 'frames', 'frame_number', 'frameno', 'time', 'f', '#frame']
    for opt in frame_options:
        if opt in cols_lower:
            frame_col = cols_lower[opt]
            break

    # X coordinate column variations
    x_options = ['x', 'x_coord', 'x_coordinate', 'xpos', 'x_position', 'x-position', 'x position']
    for opt in x_options:
        if opt in cols_lower:
            x_col = cols_lower[opt]
            break

    # Y coordinate column variations
    y_options = ['y', 'y_coord', 'y_coordinate', 'ypos', 'y_position', 'y-position', 'y position']
    for opt in y_options:
        if opt in cols_lower:
            y_col = cols_lower[opt]
            break

    # If we couldn't identify the columns by name, try to use positional logic as fallback
    if frame_col is None or x_col is None or y_col is None:
        print("  Warning: Could not identify all columns by name.")

        # Try to use numeric column names or positions as fallback
        if len(df.columns) >= 6:
            # In VBA the columns were 4, 5, 6 (1-indexed), so in 0-indexed Python we use 3, 4, 5
            try:
                frame_col = frame_col or df.columns[3]
                x_col = x_col or df.columns[4]
                y_col = y_col or df.columns[5]
                print(f"  Falling back to default column positions (4=frame, 5=x, 6=y)")
            except IndexError:
                print(f"  Error: DataFrame doesn't have enough columns for default positioning.")

        # Still couldn't identify all columns
        if frame_col is None or x_col is None or y_col is None:
            print(f"  Error: Could not identify all required columns.")
            print(f"  Available columns: {', '.join(df.columns)}")
            return None

    # Create a new DataFrame with only the required columns, renamed appropriately
    result_df = pd.DataFrame({
        'frame': df[frame_col],
        'x': df[x_col],
        'y': df[y_col]
    })

    print(f"  Using columns: '{frame_col}' as frame, '{x_col}' as x, '{y_col}' as y")

    return result_df


def calculate_normed_vectors(df):
    """Calculate normalized vectors for each step in the trajectory."""
    print("  Calculating normalized vectors...")
    start_time = time.time()

    # Create a copy with just the needed columns
    result_df = df.copy()

    # Add columns for normalized vectors
    result_df['x_vector'] = np.nan
    result_df['y_vector'] = np.nan

    # Use pandas diff to find frame discontinuities (more efficient)
    # Mark where frame numbers don't increase (indicating new trajectories)
    frame_diff = df['frame'].diff()
    new_traj_mask = (frame_diff <= 0).copy()

    # Add first row as trajectory start
    new_traj_mask.iloc[0] = True

    # Find trajectory start indices
    traj_starts = list(new_traj_mask[new_traj_mask].index)
    # Add the end of the dataframe as a boundary
    traj_starts.append(len(df))

    print(f"  Found {len(traj_starts)-1} trajectory segments")

    # Process each trajectory - using vectorized operations where possible
    for i in range(len(traj_starts) - 1):
        if i % 50 == 0 or i == len(traj_starts) - 2:  # Progress update every 50 trajectories and last one
            print(f"  Processing trajectory segment {i+1}/{len(traj_starts)-1}...")

        start_idx = traj_starts[i]
        end_idx = traj_starts[i+1]

        # Skip very short trajectories
        if end_idx - start_idx < 2:
            continue

        # Get the trajectory segment
        traj = result_df.iloc[start_idx:end_idx].copy()

        # Calculate differences between consecutive points
        dx = traj['x'].diff(-1).iloc[:-1]  # x[i] - x[i+1]
        dy = traj['y'].diff(-1).iloc[:-1]  # y[i] - y[i+1]

        # Calculate magnitudes
        magnitudes = np.sqrt(dx**2 + dy**2)

        # Find valid movements (non-zero magnitude)
        valid_moves = magnitudes > 0

        # Normalize vectors where magnitude > 0
        if len(dx) > 0:  # Avoid empty trajectories
            result_df.iloc[start_idx+1:end_idx, result_df.columns.get_loc('x_vector')] = \
                np.where(valid_moves, dx / magnitudes, np.nan)
            result_df.iloc[start_idx+1:end_idx, result_df.columns.get_loc('y_vector')] = \
                np.where(valid_moves, dy / magnitudes, np.nan)

    elapsed = time.time() - start_time
    print(f"  Normalized vectors calculated in {elapsed:.2f} seconds")

    return result_df, traj_starts


def calculate_scalar_products(df, traj_starts, time_interval, num_intervals):
    """
    Calculate scalar products of vectors for different time intervals, tracking individual trajectories.

    Args:
        df (pandas.DataFrame): DataFrame with normalized vectors
        traj_starts (list): List of indices indicating the start of each trajectory
        time_interval (float): Time interval between frames
        num_intervals (int): Number of time intervals to analyze

    Returns:
        tuple: (combined_scalar_products, individual_track_results)
            - combined_scalar_products: DataFrame with combined scalar products
            - individual_track_results: Dictionary of DataFrames with individual track scalar products
    """
    print("  Calculating scalar products...")
    start_time = time.time()

    # Initialize results dictionary (using dict for better performance than DataFrame for building)
    combined_scalar_results = {time_interval * step: [] for step in range(1, num_intervals + 1)}

    # Initialize dictionary to store individual track results
    # Structure: {track_id: {time_interval: [scalar_products]}}
    individual_track_results = {}

    # Process each trajectory
    for i in range(len(traj_starts) - 1):
        if i % 50 == 0 or i == len(traj_starts) - 2:  # Progress update every 50 trajectories and last one
            print(f"  Processing trajectory {i+1}/{len(traj_starts)-1}...")

        start_idx = traj_starts[i]
        end_idx = traj_starts[i+1]
        traj_length = end_idx - start_idx

        # Skip very short trajectories
        if traj_length < 2:
            continue

        # Create a track ID
        track_id = f"track_{i+1}"
        individual_track_results[track_id] = {}

        # Limit the number of intervals to the trajectory length
        max_intervals = min(num_intervals, traj_length)

        # Get subset of data for this trajectory
        traj_vectors = df.iloc[start_idx:end_idx]

        # For each step size
        for step in range(1, max_intervals):
            time_point = time_interval * step

            # Get vectors
            x_vecs1 = traj_vectors['x_vector'].values[:-step]
            y_vecs1 = traj_vectors['y_vector'].values[:-step]
            x_vecs2 = traj_vectors['x_vector'].values[step:]
            y_vecs2 = traj_vectors['y_vector'].values[step:]

            # Calculate dot products in a vectorized way
            dot_products = x_vecs1 * x_vecs2 + y_vecs1 * y_vecs2

            # Filter valid values (where both vectors were defined)
            valid_mask = ~np.isnan(dot_products)
            valid_dots = dot_products[valid_mask]

            # Add to combined results
            combined_scalar_results[time_point].extend(valid_dots.tolist())

            # Store for this individual track
            if len(valid_dots) > 0:
                # Calculate average correlation at this time point for this track
                track_avg_corr = np.mean(valid_dots)
                individual_track_results[track_id][time_point] = track_avg_corr

    # Convert combined results to DataFrame
    combined_df = pd.DataFrame({k: pd.Series(v) for k, v in combined_scalar_results.items()})

    # Convert individual track results to a more usable format for analysis and plotting
    # Create a DataFrame with track_id, time_interval, and correlation columns
    track_data = []
    for track_id, time_points in individual_track_results.items():
        for time_point, corr in time_points.items():
            track_data.append({
                'track_id': track_id,
                'time_interval': time_point,
                'correlation': corr
            })

    # Convert to DataFrame
    tracks_df = pd.DataFrame(track_data)

    elapsed = time.time() - start_time
    print(f"  Scalar products calculated in {elapsed:.2f} seconds")

    return combined_df, tracks_df


def calculate_averages(scalar_products):
    """Calculate averages and standard errors for each time interval."""
    # Initialize results dataframe
    results = pd.DataFrame(index=['AVG', 'SEM'])

    # Add time=0 point with perfect correlation
    results[0] = [1, 0]

    # For each time interval
    for col in scalar_products.columns:
        # Get non-NaN values
        values = scalar_products[col].dropna()

        # Calculate average
        avg = values.mean()

        # Calculate SEM
        n = len(values)
        sem = values.std() / np.sqrt(n) if n > 0 else 0

        # Add to results
        results[col] = [avg, sem]

    return results


def save_individual_track_results(tracks_df, output_dir, sheet_name, output_prefix="", file_type="excel"):
    """
    Save individual track results.

    Args:
        tracks_df (pandas.DataFrame): DataFrame with individual track results
        output_dir (str): Directory to save the file
        sheet_name (str): Name of the sheet/condition
        output_prefix (str, optional): Prefix for output filenames
        file_type (str): 'excel' or 'csv' to determine output format

    Returns:
        str: Path to the saved file
    """
    print("  Saving individual track results...")

    # Create base name
    base_name = f"{output_prefix}{sheet_name}_individual_tracks" if output_prefix else f"{sheet_name}_individual_tracks"

    # Save in the appropriate format based on input file type
    if file_type == 'excel':
        file_path = os.path.join(output_dir, f"{base_name}.xlsx")
        tracks_df.to_excel(file_path, index=False)
        print(f"  Saved individual track results to {file_path}")
    else:  # CSV
        file_path = os.path.join(output_dir, f"{base_name}.csv")
        tracks_df.to_csv(file_path, index=False)
        print(f"  Saved individual track results to {file_path}")

    return file_path


def plot_individual_tracks(tracks_df, averages, output_dir, sheet_name, output_prefix="", max_tracks=100):
    """
    Create a plot showing individual tracks alongside the average.

    Args:
        tracks_df (pandas.DataFrame): DataFrame with individual track results
        averages (pandas.DataFrame): DataFrame with average results
        output_dir (str): Directory to save the plot
        sheet_name (str): Name of the sheet/condition
        output_prefix (str, optional): Prefix for output filenames
        max_tracks (int): Maximum number of tracks to plot

    Returns:
        tuple: (png_path, pdf_path) Paths to the saved plot files
    """
    print(f"  Creating individual tracks plot for {sheet_name}...")

    plt.figure(figsize=(12, 8))

    # Get all unique track IDs
    unique_tracks = tracks_df['track_id'].unique()

    # If there are too many tracks, sample a subset
    tracks_to_plot = unique_tracks
    if len(unique_tracks) > max_tracks:
        print(f"  Sampling {max_tracks} tracks out of {len(unique_tracks)} for visualization")
        tracks_to_plot = random.sample(list(unique_tracks), max_tracks)

    # First plot individual tracks with low alpha
    # Pivot the data to get time intervals as columns and track_ids as rows
    pivot_df = tracks_df.pivot(index='track_id', columns='time_interval', values='correlation')

    # Add the time=0 point with perfect correlation for each track
    pivot_df[0] = 1.0

    # Sort columns (time intervals) numerically
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)

    # Plot each track
    for track_id in tracks_to_plot:
        if track_id in pivot_df.index:
            track_data = pivot_df.loc[track_id]
            plt.plot(track_data.index, track_data.values, '-', color='gray', alpha=0.1, linewidth=0.5)

    # Then plot the average with error bars on top
    x = np.array([float(col) for col in averages.columns])
    y = averages.loc['AVG'].values
    yerr = averages.loc['SEM'].values

    plt.errorbar(x, y, yerr=yerr, fmt='o-', color='blue', linewidth=2,
                 label='Average', markersize=6, capsize=5)

    # Set plot properties
    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title(f'{sheet_name} - Individual Tracks and Average', fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)  # Y-axis scale from config

    # Set X-axis limits
    x_max = PLOT_X_MAX if PLOT_X_MAX is not None else max(x) * 1.05
    plt.xlim(PLOT_X_MIN, x_max)

    # Add legend
    plt.legend(['Individual Tracks', 'Average (± SEM)'])

    plt.tight_layout()

    # Save plot with optional prefix
    base_name = f"{output_prefix}{sheet_name}_individual_tracks_plot" if output_prefix else f"{sheet_name}_individual_tracks_plot"
    png_path = os.path.join(output_dir, f"{base_name}.png")
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)

    print(f"  Saved individual tracks plot to {png_path}")

    plt.close()

    return png_path, pdf_path


def process_sheet(sheet_df, time_interval, num_intervals):
    """Process a single sheet (condition) from the Excel file."""
    # Identify and rename columns
    sheet_df = identify_columns(sheet_df)
    if sheet_df is None:
        return None, None, None

    # Drop rows with NaN values
    original_len = len(sheet_df)
    sheet_df = sheet_df.dropna(subset=['frame', 'x', 'y'])
    if len(sheet_df) < original_len:
        print(f"  Dropped {original_len - len(sheet_df)} rows with missing values")

    # Calculate normalized vectors
    vectors_df, traj_starts = calculate_normed_vectors(sheet_df)

    # Calculate scalar products for different time intervals, tracking individual trajectories
    scalar_products, individual_tracks = calculate_scalar_products(
        vectors_df, traj_starts, time_interval, num_intervals
    )

    # Calculate averages and standard errors
    print("  Calculating averages...")
    averages = calculate_averages(scalar_products)

    return scalar_products, averages, individual_tracks


def create_autocorrel_plot(all_results, output_dir, output_prefix="", title="Autocorrelation Analysis"):
    """Create a plot of autocorrelation results."""
    print("Creating autocorrelation plot...")
    plt.figure(figsize=(12, 8))

    # Plot each condition
    markers = ['o', 's', '^', 'd', 'v', '<', '>', 'p', '*']
    colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k']

    # Find the maximum x value across all conditions
    max_x = max([max([float(col) for col in results.columns]) for results in all_results.values()])

    for i, (condition, results) in enumerate(all_results.items()):
        # Extract x and y values
        x = np.array([float(col) for col in results.columns])
        y = results.loc['AVG'].values
        yerr = results.loc['SEM'].values

        # Select marker and color
        marker = markers[i % len(markers)]
        color = colors[i % len(colors)]

        # Plot with error bars
        plt.errorbar(x, y, yerr=yerr, fmt=f'{marker}-', capsize=5,
                     color=color, linewidth=2, label=condition, markersize=8)

    # Set plot properties
    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title(title, fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)  # Y-axis scale from config

    # Set X-axis limits
    x_max = PLOT_X_MAX if PLOT_X_MAX is not None else max_x * 1.05
    plt.xlim(PLOT_X_MIN, x_max)

    # Add legend if multiple conditions
    if len(all_results) > 1:
        plt.legend()

    plt.tight_layout()

    # Save plot with optional prefix
    plot_name = f"{output_prefix}autocorrelation_plot" if output_prefix else "autocorrelation_plot"
    png_path = os.path.join(output_dir, f"{plot_name}.png")
    pdf_path = os.path.join(output_dir, f"{plot_name}.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)

    print(f"Saved plot to {png_path}")

    plt.close()


def save_stats(all_scalar_products, output_dir, output_prefix="", file_type="excel"):
    """
    Save all scalar products for statistical analysis.

    Args:
        all_scalar_products (dict): Dictionary mapping condition names to scalar products
        output_dir (str): Directory to save the stats file
        output_prefix (str, optional): Prefix for output filenames
        file_type (str): 'excel' or 'csv' to determine output format
    """
    print("Saving statistics...")
    # Initialize a dictionary to store columns
    stats_dict = {}

    # For each condition and time interval, add a column of coefficients
    for condition, scalars in all_scalar_products.items():
        for col in scalars.columns:
            # Column name including condition and time interval
            col_name = f"{condition} - {col}"

            # Add values to stats
            values = scalars[col].dropna().values
            stats_dict[col_name] = pd.Series(values)

    # Convert to DataFrame
    stats_df = pd.DataFrame(stats_dict)

    # Create filename with optional prefix
    stats_name = f"{output_prefix}autocorrelation_stats" if output_prefix else "autocorrelation_stats"

    # Save in the appropriate format based on input file type
    if file_type == 'excel':
        stats_excel_path = os.path.join(output_dir, f"{stats_name}.xlsx")
        stats_df.to_excel(stats_excel_path, index=False)
        print(f"Saved statistics to {stats_excel_path}")
    else:  # CSV
        stats_csv_path = os.path.join(output_dir, f"{stats_name}.csv")
        stats_df.to_csv(stats_csv_path, index=False)
        print(f"Saved statistics to {stats_csv_path}")

    return stats_df


def save_averages(averages, output_dir, sheet_name, output_prefix="", file_type="excel"):
    """
    Save averages in the appropriate format.

    Args:
        averages (pandas.DataFrame): DataFrame with averages and SEMs
        output_dir (str): Directory to save the files
        sheet_name (str): Name of the sheet/condition
        output_prefix (str, optional): Prefix for output filenames
        file_type (str): 'excel' or 'csv' to determine output format
    """
    # Create base name
    base_name = f"{output_prefix}{sheet_name}_averages" if output_prefix else f"{sheet_name}_averages"

    # Save in the appropriate format based on input file type
    if file_type == 'excel':
        averages_excel_path = os.path.join(output_dir, f"{base_name}.xlsx")
        averages.to_excel(averages_excel_path)
        print(f"  Saved averages to {averages_excel_path}")
    else:  # CSV
        averages_csv_path = os.path.join(output_dir, f"{base_name}.csv")
        averages.to_csv(averages_csv_path)
        print(f"  Saved averages to {averages_csv_path}")

    return os.path.join(output_dir, f"{base_name}.{'xlsx' if file_type == 'excel' else 'csv'}")


def process_file(input_file, time_interval, num_intervals, output_dir, output_prefix=""):
    """
    Process a single file containing trajectory data.

    Args:
        input_file (str): Path to the file
        time_interval (float): Time interval between frames in minutes
        num_intervals (int): Number of time intervals to analyze
        output_dir (str): Directory to save output files
        output_prefix (str, optional): Prefix for output filenames

    Returns:
        tuple: (success flag, results dict, error message)
    """
    print(f"\nProcessing file: {os.path.basename(input_file)}")

    # Check input file
    if not os.path.exists(input_file):
        return False, None, f"Input file '{input_file}' not found."

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Read file based on type
        data_source, file_type = read_file(input_file)
        print(f"Detected file type: {file_type.upper()}")

        # Get sheet names based on file type
        if file_type == 'excel':
            sheet_names = data_source.sheet_names
        else:  # CSV
            sheet_names = list(data_source.keys())

        print(f"Found {len(sheet_names)} sheet(s)/condition(s): {', '.join(sheet_names)}")

        # Store results
        all_results = {}
        all_scalar_products = {}
        all_individual_tracks = {}
        output_files = {}

        # Process each sheet (condition)
        total_start_time = time.time()

        for sheet_name in sheet_names:
            print(f"\nProcessing sheet/condition: {sheet_name}")
            sheet_start_time = time.time()

            try:
                # Read sheet
                if file_type == 'excel':
                    sheet_df = data_source.parse(sheet_name)
                else:  # CSV
                    sheet_df = data_source[sheet_name]

                print(f"  Found {len(sheet_df)} rows of data")

                # Process sheet
                scalar_products, averages, individual_tracks = process_sheet(
                    sheet_df, time_interval, num_intervals
                )

                if scalar_products is None or averages is None:
                    print(f"  Error processing sheet {sheet_name}, skipping.")
                    continue

                # Store results
                all_results[sheet_name] = averages
                all_scalar_products[sheet_name] = scalar_products
                all_individual_tracks[sheet_name] = individual_tracks

                # Save individual results - include file prefix in name
                output_file = save_averages(
                    averages, output_dir, sheet_name, output_prefix, file_type
                )
                output_files[sheet_name] = output_file

                # Save individual track results if enabled
                if SAVE_INDIVIDUAL_TRACKS and individual_tracks is not None:
                    save_individual_track_results(
                        individual_tracks, output_dir, sheet_name, output_prefix, file_type
                    )

                # Create individual track plot if enabled
                if PLOT_INDIVIDUAL_TRACKS and individual_tracks is not None:
                    plot_individual_tracks(
                        individual_tracks, averages, output_dir, sheet_name,
                        output_prefix, MAX_TRACKS_TO_PLOT
                    )

                sheet_elapsed = time.time() - sheet_start_time
                print(f"  Sheet processed in {sheet_elapsed:.2f} seconds")

            except Exception as e:
                print(f"  Error processing sheet {sheet_name}: {str(e)}")
                traceback.print_exc()
                continue

        # Check if we have any results
        if not all_results:
            return False, None, "No valid results were generated. Check your input file format."

        print("\nCreating plots and summary statistics...")

        # Create plot
        create_autocorrel_plot(all_results, output_dir, output_prefix)

        # Save stats
        save_stats(all_scalar_products, output_dir, output_prefix, file_type)

        total_elapsed = time.time() - total_start_time
        print(f"\nAnalysis complete in {total_elapsed:.2f} seconds!")

        return True, {'results': all_results, 'scalar_products': all_scalar_products,
                      'individual_tracks': all_individual_tracks, 'file_type': file_type,
                      'output_files': output_files}, None

    except Exception as e:
        error_msg = f"Error processing file: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return False, None, error_msg


def expand_file_patterns(file_pattern):
    """
    Expand semicolon-separated file patterns into a list.

    Args:
        file_pattern (str): Semicolon-separated file patterns (e.g., "*.xlsx;*.csv")

    Returns:
        list: List of individual patterns
    """
    return file_pattern.split(';')


def aggregate_condition_results(results_list, condition_name):
    """
    Aggregate results from multiple files in a condition.

    Args:
        results_list (list): List of result dictionaries from process_file
        condition_name (str): Name of the condition

    Returns:
        tuple: (aggregated_results, file_type, aggregated_individual_tracks)
    """
    print(f"\nAggregating results for condition: {condition_name}")

    if not results_list:
        print("  No results to aggregate.")
        return None, None, None

    # Determine file type (use the first file's type)
    file_type = results_list[0]['file_type']

    # Get all time points across all results
    all_time_points = set()
    for result in results_list:
        for sheet_name, averages in result['results'].items():
            all_time_points.update([float(col) for col in averages.columns])

    all_time_points = sorted(all_time_points)

    # Create a nested dictionary to store values for each time point
    # Structure: {time_point: {file_name: value}}
    aggregated_data = defaultdict(dict)

    # For each file's results
    for i, result in enumerate(results_list):
        file_name = f"File_{i+1}"

        # For each sheet in the file
        for sheet_name, averages in result['results'].items():
            # For each time point in this sheet
            for col in averages.columns:
                time_point = float(col)
                # Store the average value
                aggregated_data[time_point][file_name] = averages.loc['AVG', col]

    # Calculate mean and SEM across files for each time point
    summary_data = {'AVG': {}, 'SEM': {}}

    for time_point in all_time_points:
        values = list(aggregated_data[time_point].values())

        if values:
            mean_value = np.mean(values)
            sem_value = np.std(values, ddof=1) / np.sqrt(len(values)) if len(values) > 1 else 0

            summary_data['AVG'][time_point] = mean_value
            summary_data['SEM'][time_point] = sem_value

    # Create summary DataFrame
    summary_df = pd.DataFrame(index=['AVG', 'SEM'])

    for time_point in all_time_points:
        summary_df[time_point] = [summary_data['AVG'][time_point], summary_data['SEM'][time_point]]

    # Aggregate individual track data from all files
    aggregated_tracks = []

    for i, result in enumerate(results_list):
        if 'individual_tracks' in result:
            for sheet_name, tracks_df in result['individual_tracks'].items():
                # Add file identifier to track_id
                tracks_df = tracks_df.copy()
                file_id = f"file_{i+1}"
                tracks_df['file_id'] = file_id
                tracks_df['track_id'] = tracks_df['track_id'] + f"_{file_id}"

                aggregated_tracks.append(tracks_df)

    # Combine all track data
    if aggregated_tracks:
        aggregated_tracks_df = pd.concat(aggregated_tracks, ignore_index=True)
    else:
        aggregated_tracks_df = None

    return summary_df, file_type, aggregated_tracks_df


def create_condition_summary(summary_df, output_dir, condition_name, file_type):
    """
    Create a summary file for a condition with mean and SEM across all files.

    Args:
        summary_df (pandas.DataFrame): DataFrame with summary statistics
        output_dir (str): Directory to save the summary file
        condition_name (str): Name of the condition
        file_type (str): 'excel' or 'csv' to determine output format

    Returns:
        str: Path to the saved summary file
    """
    print(f"Creating summary for condition: {condition_name}")

    # Create filename
    summary_name = f"{condition_name}_summary"

    # Save in the appropriate format
    if file_type == 'excel':
        summary_path = os.path.join(output_dir, f"{summary_name}.xlsx")
        summary_df.to_excel(summary_path)
        print(f"Saved condition summary to {summary_path}")
    else:  # CSV
        summary_path = os.path.join(output_dir, f"{summary_name}.csv")
        summary_df.to_csv(summary_path)
        print(f"Saved condition summary to {summary_path}")

    return summary_path


def create_condition_plot(summary_df, output_dir, condition_name):
    """
    Create a plot for a condition showing average autocorrelation and SEM.

    Args:
        summary_df (pandas.DataFrame): DataFrame with summary statistics
        output_dir (str): Directory to save the plot
        condition_name (str): Name of the condition

    Returns:
        tuple: (png_path, pdf_path) Paths to the saved plot files
    """
    print(f"Creating plot for condition: {condition_name}")

    plt.figure(figsize=(12, 8))

    # Extract x and y values
    x = np.array([float(col) for col in summary_df.columns])
    y = summary_df.loc['AVG'].values
    yerr = summary_df.loc['SEM'].values

    # Plot with error bars
    plt.errorbar(x, y, yerr=yerr, fmt='o-', capsize=5,
                 color='b', linewidth=2, markersize=8)

    # Set plot properties
    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title(f'{condition_name} Autocorrelation', fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)  # Y-axis scale from config

    # Set X-axis limits
    x_max = PLOT_X_MAX if PLOT_X_MAX is not None else max(x) * 1.05
    plt.xlim(PLOT_X_MIN, x_max)

    plt.tight_layout()

    # Save plot
    png_path = os.path.join(output_dir, f"{condition_name}_summary_plot.png")
    pdf_path = os.path.join(output_dir, f"{condition_name}_summary_plot.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)

    print(f"Saved condition plot to {png_path}")

    plt.close()

    return png_path, pdf_path


def create_condition_individual_tracks_plot(aggregated_tracks_df, summary_df, output_dir, condition_name, max_tracks=100):
    """
    Create a plot showing individual tracks from all files in a condition alongside the condition average.

    Args:
        aggregated_tracks_df (pandas.DataFrame): DataFrame with all individual track results
        summary_df (pandas.DataFrame): DataFrame with condition summary statistics
        output_dir (str): Directory to save the plot
        condition_name (str): Name of the condition
        max_tracks (int): Maximum number of tracks to plot

    Returns:
        tuple: (png_path, pdf_path) Paths to the saved plot files
    """
    if aggregated_tracks_df is None or len(aggregated_tracks_df) == 0:
        print(f"  No individual track data available for condition: {condition_name}")
        return None, None

    print(f"Creating individual tracks plot for condition: {condition_name}")

    plt.figure(figsize=(12, 8))

    # Get all unique track IDs
    unique_tracks = aggregated_tracks_df['track_id'].unique()

    # If there are too many tracks, sample a subset
    tracks_to_plot = unique_tracks
    if len(unique_tracks) > max_tracks:
        print(f"  Sampling {max_tracks} tracks out of {len(unique_tracks)} for visualization")
        tracks_to_plot = random.sample(list(unique_tracks), max_tracks)

    # Pivot the data to get time intervals as columns and track_ids as rows
    pivot_df = aggregated_tracks_df.pivot(index='track_id', columns='time_interval', values='correlation')

    # Add the time=0 point with perfect correlation for each track
    pivot_df[0] = 1.0

    # Sort columns (time intervals) numerically
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)

    # Plot each track
    for track_id in tracks_to_plot:
        if track_id in pivot_df.index:
            track_data = pivot_df.loc[track_id]
            plt.plot(track_data.index, track_data.values, '-', color='gray', alpha=0.1, linewidth=0.5)

    # Then plot the average with error bars on top
    x = np.array([float(col) for col in summary_df.columns])
    y = summary_df.loc['AVG'].values
    yerr = summary_df.loc['SEM'].values

    plt.errorbar(x, y, yerr=yerr, fmt='o-', color='blue', linewidth=2,
                 label='Average', markersize=6, capsize=5)

    # Set plot properties
    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title(f'{condition_name} - Individual Tracks and Average', fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)  # Y-axis scale from config

    # Set X-axis limits
    x_max = PLOT_X_MAX if PLOT_X_MAX is not None else max(x) * 1.05
    plt.xlim(PLOT_X_MIN, x_max)

    # Add legend
    plt.legend(['Individual Tracks', 'Average (± SEM)'])

    plt.tight_layout()

    # Save plot
    png_path = os.path.join(output_dir, f"{condition_name}_all_tracks_plot.png")
    pdf_path = os.path.join(output_dir, f"{condition_name}_all_tracks_plot.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)

    print(f"Saved condition individual tracks plot to {png_path}")

    plt.close()

    return png_path, pdf_path


def save_condition_individual_tracks(aggregated_tracks_df, output_dir, condition_name, file_type):
    """
    Save the aggregated individual track results for a condition.

    Args:
        aggregated_tracks_df (pandas.DataFrame): DataFrame with all individual track results
        output_dir (str): Directory to save the file
        condition_name (str): Name of the condition
        file_type (str): 'excel' or 'csv' to determine output format

    Returns:
        str: Path to the saved file
    """
    if aggregated_tracks_df is None or len(aggregated_tracks_df) == 0:
        print(f"  No individual track data available for condition: {condition_name}")
        return None

    print(f"Saving individual track results for condition: {condition_name}")

    # Create filename
    file_name = f"{condition_name}_all_individual_tracks"

    # Save in the appropriate format
    if file_type == 'excel':
        file_path = os.path.join(output_dir, f"{file_name}.xlsx")
        aggregated_tracks_df.to_excel(file_path, index=False)
        print(f"Saved condition individual track results to {file_path}")
    else:  # CSV
        file_path = os.path.join(output_dir, f"{file_name}.csv")
        aggregated_tracks_df.to_csv(file_path, index=False)
        print(f"Saved condition individual track results to {file_path}")

    return file_path


def process_condition_folder(input_dir, file_pattern, time_interval, num_intervals, output_dir=None):
    """
    Process all matching files in a condition folder.

    Args:
        input_dir (str): Directory containing files for a condition
        file_pattern (str): Glob pattern to match files (e.g., "*.xlsx;*.csv")
        time_interval (float): Time interval between frames in minutes
        num_intervals (int): Number of time intervals to analyze
        output_dir (str, optional): Directory to save output files. If None, a subdirectory
                                   will be created inside the input directory.

    Returns:
        tuple: (success_count, fail_count, results_list, condition_summary)
    """
    condition_name = os.path.basename(input_dir)
    print(f"\nProcessing condition folder: {condition_name}")

    # Check if directory exists
    if not os.path.isdir(input_dir):
        print(f"Error: Directory '{input_dir}' not found.")
        return 0, 0, [], None

    # Expand file patterns
    patterns = expand_file_patterns(file_pattern)

    # Find all matching files
    files = []
    for pattern in patterns:
        file_pattern_path = os.path.join(input_dir, pattern)
        files.extend(glob.glob(file_pattern_path))

    # Remove duplicates and sort
    files = sorted(list(set(files)))

    if not files:
        print(f"No files matching '{file_pattern}' found in directory.")
        return 0, 0, [], None

    print(f"Found {len(files)} file(s) matching pattern '{file_pattern}':")
    for file in files:
        print(f"  - {os.path.basename(file)}")

    # Create output directory if needed
    if output_dir is None:
        output_dir = os.path.join(input_dir, "autocorrelation_output")

    os.makedirs(output_dir, exist_ok=True)

    # Process each file
    success_count = 0
    fail_count = 0
    results_list = []

    for i, file_path in enumerate(files):
        filename = os.path.basename(file_path)
        file_base = os.path.splitext(filename)[0]

        print(f"\n[{i+1}/{len(files)}] Processing: {filename}")

        # Create output prefix based on filename (without extension)
        output_prefix = f"{file_base}_"

        success, results, error = process_file(
            file_path, time_interval, num_intervals, output_dir, output_prefix
        )

        if success and results:
            success_count += 1
            results_list.append(results)
        else:
            fail_count += 1
            print(f"Failed to process {filename}: {error}")

    # Aggregate and create condition summary if we have results
    if results_list:
        # Aggregate results across files
        summary_df, file_type, aggregated_tracks = aggregate_condition_results(
            results_list, condition_name
        )

        if summary_df is not None:
            # Create summary file
            summary_path = create_condition_summary(
                summary_df, output_dir, condition_name, file_type
            )

            # Create summary plot
            create_condition_plot(summary_df, output_dir, condition_name)

            # Save and plot individual tracks if available
            if aggregated_tracks is not None and SAVE_INDIVIDUAL_TRACKS:
                save_condition_individual_tracks(
                    aggregated_tracks, output_dir, condition_name, file_type
                )

                if PLOT_INDIVIDUAL_TRACKS:
                    create_condition_individual_tracks_plot(
                        aggregated_tracks, summary_df, output_dir,
                        condition_name, MAX_TRACKS_TO_PLOT
                    )

            print(f"\nCondition processing complete: {success_count} successful, {fail_count} failed")
            return success_count, fail_count, results_list, summary_df

    print(f"\nCondition processing complete: {success_count} successful, {fail_count} failed")
    return success_count, fail_count, results_list, None


def create_cross_condition_plot(condition_summaries, main_output_dir, experiment_dir=None):
    """
    Create a comparison plot across all conditions.

    Args:
        condition_summaries (dict): Dictionary mapping condition names to summary DataFrames
        main_output_dir (str): Directory to save the plot
        experiment_dir (str, optional): Path to the experiment directory for custom title

    Returns:
        tuple: (png_path, pdf_path) Paths to the saved plot files
    """
    print("\nCreating cross-condition comparison plot...")

    plt.figure(figsize=(12, 8))

    # Plot each condition
    markers = ['o', 's', '^', 'd', 'v', '<', '>', 'p', '*']
    colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k']

    # Find the maximum x value across all conditions
    max_x = max([max([float(col) for col in summary.columns]) for summary in condition_summaries.values()])

    for i, (condition, summary) in enumerate(condition_summaries.items()):
        # Extract x and y values
        x = np.array([float(col) for col in summary.columns])
        y = summary.loc['AVG'].values
        yerr = summary.loc['SEM'].values

        # Select marker and color
        marker = markers[i % len(markers)]
        color = colors[i % len(colors)]

        # Plot with error bars
        plt.errorbar(x, y, yerr=yerr, fmt=f'{marker}-', capsize=5,
                     color=color, linewidth=2, label=condition, markersize=8)

    # Set plot properties
    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)

    # Set plot title
    if CROSS_CONDITION_PLOT_TITLE is not None:
        # Use custom title from config
        plot_title = CROSS_CONDITION_PLOT_TITLE
    elif experiment_dir is not None:
        # Use experiment directory name as title
        plot_title = f'Comparison Across Conditions - {os.path.basename(experiment_dir)}'
    else:
        # Default title
        plot_title = 'Comparison Across Conditions'

    plt.title(plot_title, fontsize=16)

    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)  # Y-axis scale from config

    # Set X-axis limits
    x_max = PLOT_X_MAX if PLOT_X_MAX is not None else max_x * 1.05
    plt.xlim(PLOT_X_MIN, x_max)

    # Add legend
    plt.legend()

    plt.tight_layout()

    # Save plot
    png_path = os.path.join(main_output_dir, "condition_comparison_plot.png")
    pdf_path = os.path.join(main_output_dir, "condition_comparison_plot.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)

    print(f"Saved cross-condition comparison plot to {png_path}")

    plt.close()

    return png_path, pdf_path


def create_cross_condition_summary(condition_summaries, main_output_dir, file_type='csv'):
    """
    Create a summary file comparing all conditions.

    Args:
        condition_summaries (dict): Dictionary mapping condition names to summary DataFrames
        main_output_dir (str): Directory to save the summary file
        file_type (str): 'excel' or 'csv' to determine output format

    Returns:
        str: Path to the saved summary file
    """
    print("Creating cross-condition summary file...")

    # Create a new DataFrame to hold all condition data
    all_conditions_df = pd.DataFrame()

    # For each condition
    for condition, summary in condition_summaries.items():
        # Add AVG row
        avg_row = summary.loc['AVG']
        avg_row.name = f"{condition}_AVG"
        all_conditions_df = pd.concat([all_conditions_df, avg_row], axis=1)

        # Add SEM row
        sem_row = summary.loc['SEM']
        sem_row.name = f"{condition}_SEM"
        all_conditions_df = pd.concat([all_conditions_df, sem_row], axis=1)

    # Transpose for better readability
    all_conditions_df = all_conditions_df.transpose()

    # Save in the appropriate format
    if file_type == 'excel':
        summary_path = os.path.join(main_output_dir, "all_conditions_summary.xlsx")
        all_conditions_df.to_excel(summary_path)
        print(f"Saved cross-condition summary to {summary_path}")
    else:  # CSV
        summary_path = os.path.join(main_output_dir, "all_conditions_summary.csv")
        all_conditions_df.to_csv(summary_path)
        print(f"Saved cross-condition summary to {summary_path}")

    return summary_path


def process_experiment_directory(input_dir, file_pattern, time_interval, num_intervals):
    """
    Process an experiment directory containing multiple condition folders.

    Args:
        input_dir (str): Directory containing condition folders
        file_pattern (str): Glob pattern to match files (e.g., "*.xlsx;*.csv")
        time_interval (float): Time interval between frames in minutes
        num_intervals (int): Number of time intervals to analyze

    Returns:
        tuple: (success_count, fail_count, condition_summaries)
    """
    print(f"\nProcessing experiment directory: {input_dir}")

    # Check if directory exists
    if not os.path.isdir(input_dir):
        print(f"Error: Directory '{input_dir}' not found.")
        return 0, 0, {}

    # Get all subdirectories (potential condition folders)
    condition_folders = [d for d in os.listdir(input_dir)
                         if os.path.isdir(os.path.join(input_dir, d)) and not d.startswith('.')]

    if not condition_folders:
        print("No condition folders found in the experiment directory.")
        return 0, 0, {}

    print(f"Found {len(condition_folders)} condition folder(s): {', '.join(condition_folders)}")

    # Create main output directory
    main_output_dir = os.path.join(input_dir, "autocorrelation_output")
    os.makedirs(main_output_dir, exist_ok=True)

    # Process each condition folder
    total_success_count = 0
    total_fail_count = 0
    condition_summaries = {}

    for condition_folder in condition_folders:
        condition_path = os.path.join(input_dir, condition_folder)

        # Create condition-specific output directory
        condition_output_dir = os.path.join(condition_path, "autocorrelation_output")

        # Process the condition folder
        success_count, fail_count, _, summary_df = process_condition_folder(
            condition_path, file_pattern, time_interval, num_intervals, condition_output_dir
        )

        total_success_count += success_count
        total_fail_count += fail_count

        if summary_df is not None:
            condition_summaries[condition_folder] = summary_df

    # Create cross-condition comparison if we have multiple conditions
    if len(condition_summaries) > 1:
        # Create comparison plot passing experiment directory for title
        create_cross_condition_plot(condition_summaries, main_output_dir, input_dir)

        # Create comparison summary file
        create_cross_condition_summary(condition_summaries, main_output_dir)

    print(f"\nExperiment processing complete: {total_success_count} successful, {total_fail_count} failed")
    return total_success_count, total_fail_count, condition_summaries


def run_analysis(time_interval=None, num_intervals=None, input_file=None,
                input_condition_dir=None, input_experiment_dir=None,
                file_pattern="*.xlsx;*.xls;*.csv", output_dir="autocorrelation_output"):
    """
    Run autocorrelation analysis programmatically.

    Args:
        time_interval (float, optional): Time interval between frames in minutes
        num_intervals (int, optional): Number of time intervals to analyze
        input_file (str, optional): Path to a single file to process
        input_condition_dir (str, optional): Path to a single condition folder
        input_experiment_dir (str, optional): Path to an experiment directory with condition folders
        file_pattern (str, optional): Glob pattern to match files
        output_dir (str, optional): Directory to save output files

    Returns:
        bool: True if analysis was successful, False otherwise
    """
    # Print header
    print("\nAutocorrelation Analysis")
    print("=======================")

    # Validate inputs
    if time_interval is None or num_intervals is None:
        print("Error: time_interval and num_intervals must be provided.")
        return False

    if time_interval <= 0 or num_intervals <= 0:
        print("Error: time_interval and num_intervals must be positive values.")
        return False

    if input_file is not None:
        # Single file mode
        success, _, _ = process_file(input_file, time_interval, num_intervals, output_dir)
        return success

    elif input_condition_dir is not None:
        # Single condition folder mode
        success_count, _, _, _ = process_condition_folder(
            input_condition_dir, file_pattern, time_interval, num_intervals, output_dir
        )
        return success_count > 0

    elif input_experiment_dir is not None:
        # Experiment directory mode
        success_count, _, _ = process_experiment_directory(
            input_experiment_dir, file_pattern, time_interval, num_intervals
        )
        return success_count > 0

    else:
        print("Error: Either input_file, input_condition_dir, or input_experiment_dir must be provided.")
        return False


def main():
    """
    Main function with multiple modes of operation:
    1. Using config variables at the top of the script (for IDEs like Spyder)
    2. Command-line arguments
    3. GUI dialogs
    """
    # First check if config variables are set
    if (INPUT_TIME_INTERVAL is not None and INPUT_NUM_INTERVALS is not None and
        (INPUT_FILE is not None or INPUT_CONDITION_DIR is not None or INPUT_EXPERIMENT_DIR is not None)):

        # Use config variables from the top of the script
        print("Using configuration from script variables...")

        if INPUT_FILE is not None:
            # Single file mode
            success, _, _ = process_file(
                INPUT_FILE, INPUT_TIME_INTERVAL, INPUT_NUM_INTERVALS, OUTPUT_DIR
            )
            return success
        elif INPUT_CONDITION_DIR is not None:
            # Single condition folder mode
            success_count, _, _, _ = process_condition_folder(
                INPUT_CONDITION_DIR, FILE_PATTERN, INPUT_TIME_INTERVAL,
                INPUT_NUM_INTERVALS, OUTPUT_DIR
            )
            return success_count > 0
        else:
            # Experiment directory mode
            success_count, _, _ = process_experiment_directory(
                INPUT_EXPERIMENT_DIR, FILE_PATTERN, INPUT_TIME_INTERVAL,
                INPUT_NUM_INTERVALS
            )
            return success_count > 0

    # Next, check for command-line arguments
    elif len(sys.argv) > 2:
        try:
            time_interval = float(sys.argv[1])
            num_intervals = int(sys.argv[2])

            # Check if a path is specified
            if len(sys.argv) > 3:
                path = sys.argv[3]
                file_pattern = sys.argv[4] if len(sys.argv) > 4 else "*.xlsx;*.xls;*.csv"

                if os.path.isfile(path):
                    # Single file mode
                    success, _, _ = process_file(
                        path, time_interval, num_intervals, OUTPUT_DIR
                    )
                    return success
                elif os.path.isdir(path):
                    # Check if it's an experiment directory (contains subdirectories)
                    subdirs = [d for d in os.listdir(path)
                              if os.path.isdir(os.path.join(path, d)) and not d.startswith('.')]

                    if subdirs:
                        # Experiment directory mode
                        success_count, _, _ = process_experiment_directory(
                            path, file_pattern, time_interval, num_intervals
                        )
                        return success_count > 0
                    else:
                        # Single condition folder mode
                        success_count, _, _, _ = process_condition_folder(
                            path, file_pattern, time_interval, num_intervals, OUTPUT_DIR
                        )
                        return success_count > 0
                else:
                    print(f"Error: '{path}' is neither a file nor a directory.")
                    return False
            else:
                print("Error: No input file or directory specified.")
                print("Usage: python script.py time_interval num_intervals [input_path] [file_pattern]")
                return False

        except ValueError:
            print("Error: Invalid command line arguments.")
            print("Usage: python script.py time_interval num_intervals [input_path] [file_pattern]")
            return False

    # Finally, fall back to GUI
    else:
        # Get user inputs via GUI
        time_interval, num_intervals = get_user_inputs()
        if time_interval is None or num_intervals is None:
            print("Analysis cancelled.")
            return False

        # Create a basic file dialog
        root = Tk()
        root.withdraw()

        # Ask user for analysis mode
        mode = messagebox.askquestion("Analysis Mode",
                                     "Do you want to process an experiment directory with multiple condition folders?",
                                     icon='question')

        if mode == 'yes':
            # Experiment directory mode
            experiment_dir = filedialog.askdirectory(title="Select Experiment Directory (containing condition folders)")
            if not experiment_dir:
                print("No directory selected. Analysis cancelled.")
                root.destroy()
                return False

            root.destroy()

            success_count, _, _ = process_experiment_directory(
                experiment_dir, "*.xlsx;*.xls;*.csv", time_interval, num_intervals
            )
            return success_count > 0
        else:
            # Ask if processing a condition folder or single file
            submode = messagebox.askquestion("Analysis Mode",
                                          "Do you want to process a condition folder with multiple files?",
                                          icon='question')

            if submode == 'yes':
                # Condition folder mode
                condition_dir = filedialog.askdirectory(title="Select Condition Folder (containing data files)")
                if not condition_dir:
                    print("No directory selected. Analysis cancelled.")
                    root.destroy()
                    return False

                root.destroy()

                output_dir = os.path.join(condition_dir, "autocorrelation_output")

                success_count, _, _, _ = process_condition_folder(
                    condition_dir, "*.xlsx;*.xls;*.csv", time_interval, num_intervals, output_dir
                )
                return success_count > 0
            else:
                # Single file mode
                file_path = filedialog.askopenfilename(
                    title="Select Data File",
                    filetypes=[("All supported files", "*.xlsx;*.xls;*.csv"),
                              ("Excel files", "*.xlsx;*.xls"),
                              ("CSV files", "*.csv"),
                              ("All files", "*.*")]
                )

                if not file_path:
                    print("No file selected. Analysis cancelled.")
                    root.destroy()
                    return False

                root.destroy()

                success, _, _ = process_file(
                    file_path, time_interval, num_intervals, OUTPUT_DIR
                )
                return success


if __name__ == "__main__":
    main()
