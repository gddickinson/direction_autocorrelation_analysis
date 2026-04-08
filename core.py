"""
Core autocorrelation computation functions.

Contains the mathematical engine for direction autocorrelation analysis:
vector normalization, scalar product calculation, and averaging.
"""
import time
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Optional

from io_utils import identify_columns


def calculate_normed_vectors(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    """
    Calculate normalized direction vectors for each step in the trajectory.

    Splits the data into trajectory segments based on frame number resets,
    then computes unit displacement vectors within each segment.

    Args:
        df: DataFrame with 'frame', 'x', 'y' columns.

    Returns:
        Tuple of (result_df with x_vector/y_vector columns, traj_starts list).
    """
    print("  Calculating normalized vectors...")
    start_time = time.time()

    result_df = df.copy()
    result_df['x_vector'] = np.nan
    result_df['y_vector'] = np.nan

    # Handle empty input
    if len(df) == 0:
        return result_df, [0]

    # Find trajectory boundaries using frame number resets
    frame_diff = df['frame'].diff()
    new_traj_mask = (frame_diff <= 0).copy()
    new_traj_mask.iloc[0] = True

    traj_starts = list(new_traj_mask[new_traj_mask].index)
    traj_starts.append(len(df))

    print(f"  Found {len(traj_starts)-1} trajectory segments")

    for i in range(len(traj_starts) - 1):
        if i % 50 == 0 or i == len(traj_starts) - 2:
            print(f"  Processing trajectory segment {i+1}/{len(traj_starts)-1}...")

        start_idx = traj_starts[i]
        end_idx = traj_starts[i+1]

        if end_idx - start_idx < 2:
            continue

        traj = result_df.iloc[start_idx:end_idx].copy()

        dx = traj['x'].diff(-1).iloc[:-1]
        dy = traj['y'].diff(-1).iloc[:-1]
        magnitudes = np.sqrt(dx**2 + dy**2)
        valid_moves = magnitudes > 0

        if len(dx) > 0:
            result_df.iloc[start_idx+1:end_idx, result_df.columns.get_loc('x_vector')] = \
                np.where(valid_moves, dx / magnitudes, np.nan)
            result_df.iloc[start_idx+1:end_idx, result_df.columns.get_loc('y_vector')] = \
                np.where(valid_moves, dy / magnitudes, np.nan)

    elapsed = time.time() - start_time
    print(f"  Normalized vectors calculated in {elapsed:.2f} seconds")

    return result_df, traj_starts


def calculate_scalar_products(df: pd.DataFrame, traj_starts: list,
                               time_interval: float,
                               num_intervals: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate scalar products of direction vectors for different time intervals.

    Tracks results both combined (for overall statistics) and per individual
    trajectory (for individual track analysis).

    Args:
        df: DataFrame with normalized vectors (x_vector, y_vector columns).
        traj_starts: List of indices indicating the start of each trajectory.
        time_interval: Time interval between frames.
        num_intervals: Number of time intervals to analyze.

    Returns:
        Tuple of (combined_scalar_products DataFrame, individual tracks DataFrame).
    """
    print("  Calculating scalar products...")
    start_time = time.time()

    combined_scalar_results = {time_interval * step: [] for step in range(1, num_intervals + 1)}
    individual_track_results = {}

    for i in range(len(traj_starts) - 1):
        if i % 50 == 0 or i == len(traj_starts) - 2:
            print(f"  Processing trajectory {i+1}/{len(traj_starts)-1}...")

        start_idx = traj_starts[i]
        end_idx = traj_starts[i+1]
        traj_length = end_idx - start_idx

        if traj_length < 2:
            continue

        track_id = f"track_{i+1}"
        individual_track_results[track_id] = {}
        max_intervals = min(num_intervals, traj_length)
        traj_vectors = df.iloc[start_idx:end_idx]

        for step in range(1, max_intervals):
            time_point = time_interval * step

            x_vecs1 = traj_vectors['x_vector'].values[:-step]
            y_vecs1 = traj_vectors['y_vector'].values[:-step]
            x_vecs2 = traj_vectors['x_vector'].values[step:]
            y_vecs2 = traj_vectors['y_vector'].values[step:]

            dot_products = x_vecs1 * x_vecs2 + y_vecs1 * y_vecs2
            valid_mask = ~np.isnan(dot_products)
            valid_dots = dot_products[valid_mask]

            combined_scalar_results[time_point].extend(valid_dots.tolist())

            if len(valid_dots) > 0:
                track_avg_corr = np.mean(valid_dots)
                individual_track_results[track_id][time_point] = track_avg_corr

    combined_df = pd.DataFrame({k: pd.Series(v) for k, v in combined_scalar_results.items()})

    track_data = []
    for track_id, time_points in individual_track_results.items():
        for time_point, corr in time_points.items():
            track_data.append({
                'track_id': track_id,
                'time_interval': time_point,
                'correlation': corr
            })

    tracks_df = pd.DataFrame(track_data)

    elapsed = time.time() - start_time
    print(f"  Scalar products calculated in {elapsed:.2f} seconds")

    return combined_df, tracks_df


def calculate_averages(scalar_products: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate averages and standard errors for each time interval.

    Args:
        scalar_products: DataFrame with scalar products per time interval.

    Returns:
        DataFrame with 'AVG' and 'SEM' rows indexed by time interval.
    """
    results = pd.DataFrame(index=['AVG', 'SEM'])
    results[0] = [1, 0]  # Time=0: perfect correlation

    for col in scalar_products.columns:
        values = scalar_products[col].dropna()
        avg = values.mean()
        n = len(values)
        sem = values.std() / np.sqrt(n) if n > 0 else 0
        results[col] = [avg, sem]

    return results


def process_sheet(sheet_df: pd.DataFrame, time_interval: float,
                  num_intervals: int) -> Tuple[Optional[pd.DataFrame],
                                                Optional[pd.DataFrame],
                                                Optional[pd.DataFrame]]:
    """
    Process a single sheet (condition) from a data file.

    Args:
        sheet_df: Raw DataFrame from one sheet.
        time_interval: Time interval between frames.
        num_intervals: Number of time intervals to analyze.

    Returns:
        Tuple of (scalar_products, averages, individual_tracks),
        any of which may be None on failure.
    """
    sheet_df = identify_columns(sheet_df)
    if sheet_df is None:
        return None, None, None

    original_len = len(sheet_df)
    sheet_df = sheet_df.dropna(subset=['frame', 'x', 'y'])
    if len(sheet_df) < original_len:
        print(f"  Dropped {original_len - len(sheet_df)} rows with missing values")

    vectors_df, traj_starts = calculate_normed_vectors(sheet_df)
    scalar_products, individual_tracks = calculate_scalar_products(
        vectors_df, traj_starts, time_interval, num_intervals
    )

    print("  Calculating averages...")
    averages = calculate_averages(scalar_products)

    return scalar_products, averages, individual_tracks


def aggregate_condition_results(results_list: list,
                                 condition_name: str) -> Tuple[Optional[pd.DataFrame],
                                                                Optional[str],
                                                                Optional[pd.DataFrame]]:
    """
    Aggregate results from multiple files in a condition.

    Computes the mean and SEM of per-file averages across all time points,
    and combines individual track data from all files.

    Args:
        results_list: List of result dictionaries from process_file.
        condition_name: Name of the condition.

    Returns:
        Tuple of (summary_df, file_type, aggregated_tracks_df).
    """
    from collections import defaultdict

    print(f"\nAggregating results for condition: {condition_name}")

    if not results_list:
        print("  No results to aggregate.")
        return None, None, None

    file_type = results_list[0]['file_type']

    all_time_points = set()
    for result in results_list:
        for sheet_name, averages in result['results'].items():
            all_time_points.update([float(col) for col in averages.columns])

    all_time_points = sorted(all_time_points)

    aggregated_data = defaultdict(dict)
    for i, result in enumerate(results_list):
        file_name = f"File_{i+1}"
        for sheet_name, averages in result['results'].items():
            for col in averages.columns:
                time_point = float(col)
                aggregated_data[time_point][file_name] = averages.loc['AVG', col]

    summary_data = {'AVG': {}, 'SEM': {}}
    for time_point in all_time_points:
        values = list(aggregated_data[time_point].values())
        if values:
            mean_value = np.mean(values)
            sem_value = np.std(values, ddof=1) / np.sqrt(len(values)) if len(values) > 1 else 0
            summary_data['AVG'][time_point] = mean_value
            summary_data['SEM'][time_point] = sem_value

    summary_df = pd.DataFrame(index=['AVG', 'SEM'])
    for time_point in all_time_points:
        summary_df[time_point] = [summary_data['AVG'][time_point], summary_data['SEM'][time_point]]

    # Aggregate individual track data
    aggregated_tracks = []
    for i, result in enumerate(results_list):
        if 'individual_tracks' in result:
            for sheet_name, tracks_df in result['individual_tracks'].items():
                tracks_df = tracks_df.copy()
                file_id = f"file_{i+1}"
                tracks_df['file_id'] = file_id
                tracks_df['track_id'] = tracks_df['track_id'] + f"_{file_id}"
                aggregated_tracks.append(tracks_df)

    if aggregated_tracks:
        aggregated_tracks_df = pd.concat(aggregated_tracks, ignore_index=True)
    else:
        aggregated_tracks_df = None

    return summary_df, file_type, aggregated_tracks_df
