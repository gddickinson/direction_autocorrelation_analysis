#!/usr/bin/env python3
"""
trajectory_analyzer.py - Calculate trajectory metrics including sRg, shape parameters, and linearity metrics

This script calculates trajectory metrics for 2D particle tracks in CSV files:
- Radius of gyration (Rg) using either simple or tensor-based methods
- Scaled radius of gyration (sRg)
- Asymmetry, skewness, and kurtosis (with tensor method)
- Linear motion metrics: eigenvalue ratio, directionality ratio, step alignment

The script can also output mobile tracks split by classification for further analysis.

Usage in Spyder:
  1. Edit the CONFIG section below
  2. Run the script

Command-line usage:
  python trajectory_analyzer.py --file <path_to_csv>
  python trajectory_analyzer.py --directory <path_to_dir>
  python trajectory_analyzer.py --split-outputs --mobile-only
  python trajectory_analyzer.py --help

The input CSV should have at least these columns: track_number, frame, x, y
Output will be saved as <original_filename>_metrics.csv
Split outputs will be saved as:
  - <original_filename>_mobile_linear.csv
  - <original_filename>_mobile_nonlinear.csv
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
import math
from scipy import stats
from pathlib import Path

#######################################################################
# CONFIG SECTION - Edit these variables when running in Spyder
#######################################################################
# Set to True to use direct execution in Spyder (False for command line)
USE_DIRECT_EXECUTION = True

# Choose single file or directory mode ('file' or 'directory')
#EXECUTION_MODE = 'file'
EXECUTION_MODE = 'directory'

# Path to single file (for EXECUTION_MODE = 'file')
FILE_PATH = None
#FILE_PATH = r"/Users/george/Desktop/testing_linearity_bin20/GB_173_2022_04_22_HTEndothelial_BAPTA_plate3_GoF_yoda1_5_bin20_locsID_tracksRG.csv"  # Use raw string with r prefix

# Path to directory with CSV files (for EXECUTION_MODE = 'directory')
#DIRECTORY_PATH = None
DIRECTORY_PATH = r"/Users/george/Desktop/gabby_10ms_data_bin20/linearity/GoF_Yoda1"  # Use raw string with r prefix

# Analysis parameters
CUTOFF_LEN = 3  # Minimum trajectory length
#SRG_CUTOFF = 2.22236433588659  # Threshold for mobile/immobile classification
SRG_CUTOFF = 1.2 # Threshold for mobile/immobile classification
LINEAR_EIGENVALUE_RATIO_CUTOFF = 20.0  # Threshold for linear/non-linear classification
LINEAR_STEP_ALIGNMENT_CUTOFF = 0.7  # Threshold for step alignment (cosine similarity)

# Analysis options
RG_METHOD = 'tensor'  # 'simple' or 'tensor'
INCLUDE_SHAPE_METRICS = True  # Include asymmetry, skewness, and kurtosis
INCLUDE_LINEAR_METRICS = True  # Include linear motion metrics

# Output options
OUTPUT_SUFFIX = '_metrics'  # Suffix for output filenames
SPLIT_OUTPUTS = True  # Create separate files for different classifications
GENERATE_STATS = True  # Generate statistics summary file
MOBILE_ONLY = True  # Only include mobile tracks in split outputs
OUTPUT_DIR = None  # Directory for output files (None = same as input)
#######################################################################


def get_radius_of_gyration_simple(xy):
    """Calculate radius of gyration using simple formula.

    Args:
        xy: Nx2 matrix of coordinates (can contain NaN values)

    Returns:
        Radius of gyration value
    """
    # Remove NaN values
    xy = xy[~np.isnan(xy).any(axis=1)]

    if len(xy) < 2:
        return np.nan

    # Calculate average position
    avg = np.nanmean(xy, axis=0)

    # Calculate average squared position
    avg2 = np.nanmean(xy**2, axis=0)

    # Calculate radius of gyration
    rg = np.sqrt(np.sum(avg2 - avg**2))

    return rg


def get_trajectory_metrics_tensor(xy):
    """Calculate radius of gyration, shape metrics, and linear motion metrics using tensor-based approach.

    Args:
        xy: Nx2 matrix of coordinates (can contain NaN values)

    Returns:
        Dictionary with metrics: rg, asymmetry, skewness, kurtosis,
        eigenvalue_ratio, step_alignment, and linear_classification
    """
    # Remove NaN values
    xy = xy[~np.isnan(xy).any(axis=1)]

    num_points = len(xy)
    if num_points < 2:
        return {
            'rg': np.nan,
            'asymmetry': np.nan,
            'skewness': np.nan,
            'kurtosis': np.nan,
            'eigenvalue_ratio': np.nan,
            'step_alignment': np.nan,
            'directionality_ratio': np.nan
        }

    # Calculate center
    center = np.mean(xy, axis=0)

    # Center the coordinates
    normed_points = xy - center[None, :]

    # Calculate gyration tensor
    gyration_tensor = np.einsum('im,in->mn', normed_points, normed_points) / num_points

    # Get eigenvalues and eigenvectors
    eig_values, eig_vectors = np.linalg.eig(gyration_tensor)

    # Ensure eigenvalues are real (they should be, as gyration tensor is symmetric)
    eig_values = np.real(eig_values)

    # Sort eigenvalues and corresponding eigenvectors in descending order
    idx = eig_values.argsort()[::-1]
    eig_values = eig_values[idx]
    eig_vectors = eig_vectors[:, idx]

    # Ensure eigenvectors are real
    eig_vectors = np.real(eig_vectors)

    # Radius of gyration is square root of sum of eigenvalues
    rg = np.sqrt(np.sum(eig_values))

    # Calculate asymmetry
    try:
        asymmetry_numerator = pow((eig_values[0] - eig_values[1]), 2)
        asymmetry_denominator = 2 * (pow((eig_values[0] + eig_values[1]), 2))
        asymmetry = - math.log(1 - (asymmetry_numerator / asymmetry_denominator))
    except (ValueError, ZeroDivisionError):
        asymmetry = np.nan

    # Calculate skewness and kurtosis
    try:
        # Principal eigenvector (corresponds to largest eigenvalue)
        principal_eigenvector = eig_vectors[:, 0]

        # Calculate step vectors
        points_a = xy[:-1]
        points_b = xy[1:]
        steps = points_b - points_a

        # Project steps onto principal eigenvector
        proj_steps = np.dot(steps, principal_eigenvector) / np.linalg.norm(principal_eigenvector)

        # Calculate skewness and kurtosis of step projections
        skewness = stats.skew(proj_steps)
        kurtosis = stats.kurtosis(proj_steps)
    except (ValueError, ZeroDivisionError):
        skewness = np.nan
        kurtosis = np.nan
        proj_steps = np.array([])

    # Calculate eigenvalue ratio (λ₁/λ₂) - key indicator for linear motion
    try:
        eigenvalue_ratio = eig_values[0] / eig_values[1] if eig_values[1] > 0 else np.inf
    except (IndexError, ZeroDivisionError):
        eigenvalue_ratio = np.nan

    # Calculate step alignment with principal axis
    try:
        # Normalize step vectors
        step_norms = np.linalg.norm(steps, axis=1)
        valid_steps = step_norms > 0
        normalized_steps = steps[valid_steps] / step_norms[valid_steps, None]

        # Calculate absolute cosine similarity between steps and principal eigenvector
        cos_angles = np.abs(np.dot(normalized_steps, principal_eigenvector))

        # Average alignment
        step_alignment = np.mean(cos_angles)
    except (ValueError, ZeroDivisionError, IndexError):
        step_alignment = np.nan

    # Calculate directionality ratio (net displacement / total path length)
    try:
        net_displacement = np.linalg.norm(xy[-1] - xy[0])
        path_length = np.sum(np.linalg.norm(steps, axis=1))
        directionality_ratio = net_displacement / path_length if path_length > 0 else np.nan
    except (ValueError, ZeroDivisionError, IndexError):
        directionality_ratio = np.nan

    return {
        'rg': rg,
        'asymmetry': asymmetry,
        'skewness': skewness,
        'kurtosis': kurtosis,
        'eigenvalue_ratio': eigenvalue_ratio,
        'step_alignment': step_alignment,
        'directionality_ratio': directionality_ratio
    }


def get_mean_step_length(xy):
    """Calculate mean step length of trajectory.

    Args:
        xy: Nx2 matrix of coordinates (can contain NaN values)

    Returns:
        Mean step length
    """
    # Remove NaN values
    xy = xy[~np.isnan(xy).any(axis=1)]

    if len(xy) < 2:
        return np.nan

    # Calculate steps
    steps = np.diff(xy, axis=0)

    # Calculate step lengths
    step_lengths = np.sqrt(np.sum(steps**2, axis=1))

    # Return mean step length
    return np.mean(step_lengths)


def get_scaled_rg(rg, mean_step_length):
    """Calculate scaled radius of gyration as in Golan and Sherman Nat Comm 2017.

    Args:
        rg: Radius of gyration
        mean_step_length: Mean step length

    Returns:
        Scaled radius of gyration value
    """
    if np.isnan(rg) or np.isnan(mean_step_length) or mean_step_length == 0:
        return np.nan

    s_rg = np.sqrt(np.pi/2) * rg / mean_step_length
    return s_rg


def classify_linear_motion(eigenvalue_ratio, step_alignment, directionality_ratio):
    """Classify trajectory as linear or non-linear based on eigenvalue ratio and step alignment.

    Args:
        eigenvalue_ratio: Ratio of largest to smallest eigenvalue
        step_alignment: Average absolute cosine similarity between steps and principal eigenvector
        directionality_ratio: Net displacement divided by total path length

    Returns:
        Classification (string): 'linear_unidirectional', 'linear_bidirectional', or 'non_linear'
    """
    # Check if metrics are valid
    if np.isnan(eigenvalue_ratio) or np.isnan(step_alignment):
        return 'unclassified'

    # Check for linear motion based on eigenvalue ratio and step alignment
    is_linear = (eigenvalue_ratio >= LINEAR_EIGENVALUE_RATIO_CUTOFF and
                step_alignment >= LINEAR_STEP_ALIGNMENT_CUTOFF)

    if not is_linear:
        return 'non_linear'

    # Distinguish between unidirectional and bidirectional linear motion
    if np.isnan(directionality_ratio):
        return 'linear'

    # High directionality ratio suggests unidirectional motion
    # A perfect line from start to end would have directionality_ratio = 1
    if directionality_ratio >= 0.7:  # Threshold can be adjusted
        return 'linear_unidirectional'
    else:
        return 'linear_bidirectional'


def process_csv_file(file_path, cutoff_len=3, sRg_cutoff=2.22236433588659,
                     linear_eig_ratio_cutoff=5.0, linear_step_align_cutoff=0.7,
                     method='tensor', include_shape_metrics=True, include_linear_metrics=True):
    """Process a single CSV file to calculate trajectory metrics.

    Args:
        file_path: Path to CSV file
        cutoff_len: Minimum trajectory length
        sRg_cutoff: Threshold for mobile/immobile classification
        linear_eig_ratio_cutoff: Threshold for eigenvalue ratio in linear classification
        linear_step_align_cutoff: Threshold for step alignment in linear classification
        method: Method to calculate Rg ('simple' or 'tensor')
        include_shape_metrics: Whether to include shape metrics in output
        include_linear_metrics: Whether to include linear motion metrics in output

    Returns:
        DataFrame with original data plus metrics columns
    """
    print(f"Processing {file_path}")
    print(f"Using {method} method for Rg calculation")

    # Set global thresholds for linear motion detection
    global LINEAR_EIGENVALUE_RATIO_CUTOFF, LINEAR_STEP_ALIGNMENT_CUTOFF
    LINEAR_EIGENVALUE_RATIO_CUTOFF = linear_eig_ratio_cutoff
    LINEAR_STEP_ALIGNMENT_CUTOFF = linear_step_align_cutoff

    try:
        # Read the CSV file
        df = pd.read_csv(file_path)

        # Check if required columns exist
        required_cols = ['track_number', 'frame', 'x', 'y']
        if not all(col in df.columns for col in required_cols):
            print(f"Error: Missing required columns in {file_path}")
            return None

        # Split data by track_number
        tracks = df.groupby('track_number')

        # Only process tracks with length >= cutoff_len
        track_lens = tracks.size()
        selected_tracks = track_lens[track_lens >= cutoff_len].index.tolist()

        print(f"Found {len(selected_tracks)} tracks with length >= {cutoff_len}")

        # Calculate metrics for each selected track
        results = []
        for track_num in selected_tracks:
            track_data = tracks.get_group(track_num)
            track_data = track_data.sort_values('frame')

            # Create trajectory matrix with potential gaps
            frames = track_data['frame'].values
            min_frame = frames.min()
            max_frame = frames.max()

            traj_len = max_frame - min_frame + 1
            traj_matrix = np.full((traj_len, 2), np.nan)

            # Fill in the matrix with available coordinates
            frame_indices = frames - min_frame
            traj_matrix[frame_indices, 0] = track_data['x'].values
            traj_matrix[frame_indices, 1] = track_data['y'].values

            # Calculate mean step length
            mean_step = get_mean_step_length(traj_matrix)

            # Calculate Rg and other metrics based on selected method
            if method == 'simple':
                rg = get_radius_of_gyration_simple(traj_matrix)
                metrics = {
                    'rg': rg,
                    'asymmetry': np.nan,
                    'skewness': np.nan,
                    'kurtosis': np.nan,
                    'eigenvalue_ratio': np.nan,
                    'step_alignment': np.nan,
                    'directionality_ratio': np.nan
                }
            else:  # tensor method
                metrics = get_trajectory_metrics_tensor(traj_matrix)
                rg = metrics['rg']

            # Calculate sRg
            srg_value = get_scaled_rg(rg, mean_step)

            # Determine mobility classification
            mobility_classification = 'immobile' if srg_value < sRg_cutoff else 'mobile'

            # Determine linearity classification
            if method == 'tensor' and include_linear_metrics:
                linear_classification = classify_linear_motion(
                    metrics['eigenvalue_ratio'],
                    metrics['step_alignment'],
                    metrics['directionality_ratio']
                )
            else:
                linear_classification = 'unclassified'

            # Create result dictionary
            result = {
                'track_number': track_num,
                'rg': rg,
                'mean_step_length': mean_step,
                'sRg': srg_value,
                'mobility_classification': mobility_classification,
                'linear_classification': linear_classification
            }

            # Add shape metrics if requested
            if include_shape_metrics and method == 'tensor':
                result['asymmetry'] = metrics['asymmetry']
                result['skewness'] = metrics['skewness']
                result['kurtosis'] = metrics['kurtosis']

            # Add linear motion metrics if requested
            if include_linear_metrics and method == 'tensor':
                result['eigenvalue_ratio'] = metrics['eigenvalue_ratio']
                result['step_alignment'] = metrics['step_alignment']
                result['directionality_ratio'] = metrics['directionality_ratio']

            results.append(result)

        # Create DataFrame with results
        metrics_df = pd.DataFrame(results)

        # Merge with original data
        merged_df = pd.merge(df, metrics_df, on='track_number', how='left')

        # Sort the merged data
        merged_df = merged_df.sort_values(['track_number', 'frame'])

        return merged_df

    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def save_processed_data(df, file_path, suffix='_metrics', split_outputs=False, mobile_only=False, output_dir=None, stats_data=None):
    """Save processed data to a new CSV file.

    Args:
        df: DataFrame with metrics
        file_path: Original file path
        suffix: Suffix for the output filename
        split_outputs: Whether to split output by classification
        mobile_only: Whether to only include mobile tracks in split outputs
        output_dir: Directory for output files (None = 'results' subdirectory in input folder)
        stats_data: Optional dictionary to collect statistics (for stats file generation)
    """
    # Create new filename
    path = Path(file_path)

    # Use specified output directory if provided, otherwise create 'results' subdirectory
    if output_dir:
        output_path = Path(output_dir)
    else:
        # Create 'results' subdirectory in the input directory
        output_path = path.parent / 'results'

    # Create directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    # Save full metrics file
    new_filename = output_path / f"{path.stem}{suffix}{path.suffix}"
    df.to_csv(new_filename, index=False)
    print(f"Saved results to {new_filename}")

    # Collect statistics for this file if stats_data is provided
    if stats_data is not None and isinstance(stats_data, dict) and 'sRg' in df.columns:
        collect_file_statistics(df, path.stem, stats_data)

    # Split outputs by classification if requested
    if split_outputs and 'mobility_classification' in df.columns and 'linear_classification' in df.columns:
        # Filter for mobile tracks
        mobile_df = df[df['mobility_classification'] == 'mobile'].copy()

        # Create 'mobile' directory for all mobile tracks
        mobile_dir = output_path / 'mobile'
        mobile_dir.mkdir(parents=True, exist_ok=True)

        # Save all mobile tracks
        if not mobile_df.empty:
            mobile_filename = mobile_dir / f"{path.stem}_mobile{path.suffix}"
            mobile_df.to_csv(mobile_filename, index=False)
            print(f"Saved {len(mobile_df['track_number'].unique())} mobile tracks to {mobile_filename}")

        # Use mobile_only mode for further splitting
        if mobile_only:
            df_split = mobile_df
            mobility_prefix = 'mobile'
        else:
            df_split = df.copy()
            mobility_prefix = 'all'

        # Get unique track numbers for each classification
        # Fix: Use explicit filtering to avoid matching "non_linear" when looking for linear tracks
        linear_tracks = df_split[df_split['linear_classification'].isin(['linear', 'linear_unidirectional', 'linear_bidirectional'])]['track_number'].unique()
        nonlinear_tracks = df_split[df_split['linear_classification'] == 'non_linear']['track_number'].unique()

        # Create and save linear tracks file
        if len(linear_tracks) > 0:
            # Create subdirectory for linear tracks
            linear_dir = output_path / f"{mobility_prefix}_linear"
            linear_dir.mkdir(parents=True, exist_ok=True)

            linear_df = df[df['track_number'].isin(linear_tracks)]
            # Keep the classification in the filename
            linear_filename = linear_dir / f"{path.stem}_{mobility_prefix}_linear{path.suffix}"
            linear_df.to_csv(linear_filename, index=False)
            print(f"Saved {len(linear_tracks)} linear tracks to {linear_filename}")
        else:
            print(f"No linear tracks found for {file_path}")

        # Create and save non-linear tracks file
        if len(nonlinear_tracks) > 0:
            # Create subdirectory for non-linear tracks
            nonlinear_dir = output_path / f"{mobility_prefix}_nonlinear"
            nonlinear_dir.mkdir(parents=True, exist_ok=True)

            nonlinear_df = df[df['track_number'].isin(nonlinear_tracks)]
            # Keep the classification in the filename
            nonlinear_filename = nonlinear_dir / f"{path.stem}_{mobility_prefix}_nonlinear{path.suffix}"
            nonlinear_df.to_csv(nonlinear_filename, index=False)
            print(f"Saved {len(nonlinear_tracks)} non-linear tracks to {nonlinear_filename}")
        else:
            print(f"No non-linear tracks found for {file_path}")

        # Optionally, split linear tracks into unidirectional and bidirectional
        uni_tracks = df_split[df_split['linear_classification'] == 'linear_unidirectional']['track_number'].unique()
        bidir_tracks = df_split[df_split['linear_classification'] == 'linear_bidirectional']['track_number'].unique()

        if len(uni_tracks) > 0:
            # Create subdirectory for unidirectional linear tracks
            uni_dir = output_path / f"{mobility_prefix}_linear_unidirectional"
            uni_dir.mkdir(parents=True, exist_ok=True)

            uni_df = df[df['track_number'].isin(uni_tracks)]
            # Keep the classification in the filename
            uni_filename = uni_dir / f"{path.stem}_{mobility_prefix}_linear_unidirectional{path.suffix}"
            uni_df.to_csv(uni_filename, index=False)
            print(f"Saved {len(uni_tracks)} unidirectional linear tracks to {uni_filename}")

        if len(bidir_tracks) > 0:
            # Create subdirectory for bidirectional linear tracks
            bidir_dir = output_path / f"{mobility_prefix}_linear_bidirectional"
            bidir_dir.mkdir(parents=True, exist_ok=True)

            bidir_df = df[df['track_number'].isin(bidir_tracks)]
            # Keep the classification in the filename
            bidir_filename = bidir_dir / f"{path.stem}_{mobility_prefix}_linear_bidirectional{path.suffix}"
            bidir_df.to_csv(bidir_filename, index=False)
            print(f"Saved {len(bidir_tracks)} bidirectional linear tracks to {bidir_filename}")


def collect_file_statistics(df, filename, stats_data):
    """Collect statistics for a processed file for later stats reporting.

    Args:
        df: DataFrame with metrics
        filename: Name of the file (without path)
        stats_data: Dictionary to store the statistics
    """
    # Make sure file entry exists in stats_data
    if filename not in stats_data:
        stats_data[filename] = {}

    # Count total tracks
    total_tracks = df['track_number'].nunique()
    stats_data[filename]['total_tracks'] = total_tracks

    # Calculate mobility statistics
    if 'mobility_classification' in df.columns:
        # Group by track and get first occurrence of classification (same for all rows in track)
        track_mobility = df.groupby('track_number')['mobility_classification'].first()

        # Count mobile and immobile tracks
        mobile_tracks = (track_mobility == 'mobile').sum()
        immobile_tracks = (track_mobility == 'immobile').sum()

        # Calculate percentages
        pct_mobile = (mobile_tracks / total_tracks) * 100 if total_tracks > 0 else 0
        pct_immobile = (immobile_tracks / total_tracks) * 100 if total_tracks > 0 else 0

        # Store counts and percentages
        stats_data[filename]['mobile_tracks'] = mobile_tracks
        stats_data[filename]['immobile_tracks'] = immobile_tracks
        stats_data[filename]['pct_mobile'] = pct_mobile
        stats_data[filename]['pct_immobile'] = pct_immobile

    # Calculate linearity statistics for mobile tracks
    if 'mobility_classification' in df.columns and 'linear_classification' in df.columns:
        # Filter for mobile tracks first
        mobile_df = df[df['mobility_classification'] == 'mobile']
        mobile_total = mobile_df['track_number'].nunique()

        # Group by track and get first occurrence of classification
        track_linearity = mobile_df.groupby('track_number')['linear_classification'].first()

        # Count different types of linear and non-linear tracks
        linear_tracks = sum(track_linearity.isin(['linear', 'linear_unidirectional', 'linear_bidirectional']))
        nonlinear_tracks = sum(track_linearity == 'non_linear')
        unidirectional_tracks = sum(track_linearity == 'linear_unidirectional')
        bidirectional_tracks = sum(track_linearity == 'linear_bidirectional')

        # Calculate percentages of mobile tracks
        pct_linear = (linear_tracks / mobile_total) * 100 if mobile_total > 0 else 0
        pct_nonlinear = (nonlinear_tracks / mobile_total) * 100 if mobile_total > 0 else 0
        #Percent of total mobile
        #pct_unidirectional = (unidirectional_tracks / mobile_total) * 100 if mobile_total > 0 else 0
        #pct_bidirectional = (bidirectional_tracks / mobile_total) * 100 if mobile_total > 0 else 0
        #Percent of linear
        pct_unidirectional = (unidirectional_tracks / linear_tracks) * 100 if mobile_total > 0 else 0
        pct_bidirectional = (bidirectional_tracks / linear_tracks) * 100 if mobile_total > 0 else 0

        # Store counts and percentages
        stats_data[filename]['linear_tracks'] = linear_tracks
        stats_data[filename]['nonlinear_tracks'] = nonlinear_tracks
        stats_data[filename]['unidirectional_tracks'] = unidirectional_tracks
        stats_data[filename]['bidirectional_tracks'] = bidirectional_tracks
        stats_data[filename]['pct_linear'] = pct_linear
        stats_data[filename]['pct_nonlinear'] = pct_nonlinear
        stats_data[filename]['pct_unidirectional'] = pct_unidirectional
        stats_data[filename]['pct_bidirectional'] = pct_bidirectional

    # Calculate sRg statistics
    if 'sRg' in df.columns:
        # All tracks sRg
        all_srg = df.groupby('track_number')['sRg'].first().dropna()
        stats_data[filename]['mean_sRg_all'] = all_srg.mean()
        stats_data[filename]['se_sRg_all'] = all_srg.sem()

        # Mobile tracks sRg
        if 'mobility_classification' in df.columns:
            mobile_tracks = df[df['mobility_classification'] == 'mobile']['track_number'].unique()
            mobile_srg = df[df['track_number'].isin(mobile_tracks)].groupby('track_number')['sRg'].first().dropna()
            stats_data[filename]['mean_sRg_mobile'] = mobile_srg.mean()
            stats_data[filename]['se_sRg_mobile'] = mobile_srg.sem()

    # Calculate rg statistics
    if 'rg' in df.columns:
        # All tracks rg
        all_rg = df.groupby('track_number')['rg'].first().dropna()
        stats_data[filename]['mean_rg_all'] = all_rg.mean()
        stats_data[filename]['se_rg_all'] = all_rg.sem()

        # Mobile tracks rg
        if 'mobility_classification' in df.columns:
            mobile_tracks = df[df['mobility_classification'] == 'mobile']['track_number'].unique()
            mobile_rg = df[df['track_number'].isin(mobile_tracks)].groupby('track_number')['rg'].first().dropna()
            stats_data[filename]['mean_rg_mobile'] = mobile_rg.mean()
            stats_data[filename]['se_rg_mobile'] = mobile_rg.sem()

    # Calculate step length statistics
    if 'mean_step_length' in df.columns:
        # All tracks step length
        all_step = df.groupby('track_number')['mean_step_length'].first().dropna()
        stats_data[filename]['mean_step_length_all'] = all_step.mean()
        stats_data[filename]['se_step_length_all'] = all_step.sem()

        # Mobile tracks step length
        if 'mobility_classification' in df.columns:
            mobile_tracks = df[df['mobility_classification'] == 'mobile']['track_number'].unique()
            mobile_step = df[df['track_number'].isin(mobile_tracks)].groupby('track_number')['mean_step_length'].first().dropna()
            stats_data[filename]['mean_step_length_mobile'] = mobile_step.mean()
            stats_data[filename]['se_step_length_mobile'] = mobile_step.sem()


def generate_stats_file(stats_data, directory_path):
    """Generate a statistics summary file from collected data.

    Args:
        stats_data: Dictionary containing statistics data
        directory_path: Path to save the stats file
    """
    if not stats_data:
        print("No statistics data available")
        return

    # Convert stats_data dictionary to DataFrame
    stats_df = pd.DataFrame.from_dict(stats_data, orient='index')

    # Calculate aggregate statistics (mean across all files)
    aggregate_stats = {}
    numeric_columns = stats_df.select_dtypes(include=[np.number]).columns

    for col in numeric_columns:
        aggregate_stats[f'mean_{col}'] = stats_df[col].mean()
        aggregate_stats[f'se_{col}'] = stats_df[col].sem()

    # Add a row with aggregate statistics
    stats_df.loc['AGGREGATE'] = pd.Series(aggregate_stats)

    # Save to CSV
    output_path = Path(directory_path) / 'results'
    output_path.mkdir(parents=True, exist_ok=True)
    stats_file = output_path / 'experiment_statistics.csv'
    stats_df.to_csv(stats_file)
    print(f"Saved statistics summary to {stats_file}")

def process_directory(directory_path, cutoff_len=3, sRg_cutoff=2.22236433588659,
                      linear_eig_ratio_cutoff=5.0, linear_step_align_cutoff=0.7,
                      method='tensor', include_shape_metrics=True, include_linear_metrics=True,
                      suffix='_metrics', split_outputs=False, mobile_only=False, output_dir=None,
                      generate_stats=False):
    """Process all CSV files in a directory.

    Args:
        directory_path: Path to directory containing CSV files
        cutoff_len: Minimum trajectory length
        sRg_cutoff: Threshold for mobile/immobile classification
        linear_eig_ratio_cutoff: Threshold for eigenvalue ratio in linear classification
        linear_step_align_cutoff: Threshold for step alignment in linear classification
        method: Method to calculate Rg ('simple' or 'tensor')
        include_shape_metrics: Whether to include shape metrics in output
        include_linear_metrics: Whether to include linear motion metrics in output
        suffix: Suffix for the output filenames
        split_outputs: Whether to split output by classification
        mobile_only: Whether to only include mobile tracks in split outputs
        output_dir: Directory for output files (None = same as input)
        generate_stats: Whether to generate a statistics summary file
    """
    directory = Path(directory_path)

    if not directory.exists() or not directory.is_dir():
        print(f"Error: Directory {directory_path} does not exist")
        return

    # Get all CSV files in directory
    csv_files = list(directory.glob("*.csv"))

    if not csv_files:
        print(f"No CSV files found in {directory_path}")
        return

    print(f"Found {len(csv_files)} CSV files in {directory_path}")

    # Initialize stats_data dictionary if generating stats
    stats_data = {} if generate_stats else None

    # Process each file
    for file_path in csv_files:
        # Skip files that already have the suffix in the filename
        if suffix in file_path.stem:
            print(f"Skipping already processed file: {file_path}")
            continue

        # Process the file
        df = process_csv_file(file_path, cutoff_len, sRg_cutoff,
                             linear_eig_ratio_cutoff, linear_step_align_cutoff,
                             method, include_shape_metrics, include_linear_metrics)

        if df is not None:
            save_processed_data(df, file_path, suffix, split_outputs, mobile_only, output_dir, stats_data)

    # Generate statistics summary file if requested
    if generate_stats and stats_data:
        generate_stats_file(stats_data, directory_path)

    print("Batch processing complete.")


def run_script(mode, path, cutoff_len=3, sRg_cutoff=2.22236433588659,
               linear_eig_ratio_cutoff=5.0, linear_step_align_cutoff=0.7,
               method='tensor', include_shape_metrics=True, include_linear_metrics=True,
               suffix='_metrics', split_outputs=False, mobile_only=False, output_dir=None,
               generate_stats=False):
    """Run the script with the specified parameters.

    Args:
        mode: 'file' or 'directory'
        path: Path to file or directory
        cutoff_len: Minimum trajectory length
        sRg_cutoff: Threshold for mobile/immobile classification
        linear_eig_ratio_cutoff: Threshold for eigenvalue ratio in linear classification
        linear_step_align_cutoff: Threshold for step alignment in linear classification
        method: Method to calculate Rg ('simple' or 'tensor')
        include_shape_metrics: Whether to include shape metrics in output
        include_linear_metrics: Whether to include linear motion metrics in output
        suffix: Suffix for the output filenames
        split_outputs: Whether to split output by classification
        mobile_only: Whether to only include mobile tracks in split outputs
        output_dir: Directory for output files (None = same as input)
        generate_stats: Whether to generate a statistics summary file
    """
    if mode == 'file':
        df = process_csv_file(path, cutoff_len, sRg_cutoff,
                             linear_eig_ratio_cutoff, linear_step_align_cutoff,
                             method, include_shape_metrics, include_linear_metrics)
        if df is not None:
            # Use an empty stats_data dictionary for single file analysis if stats are requested
            stats_data = {} if generate_stats else None
            save_processed_data(df, path, suffix, split_outputs, mobile_only, output_dir, stats_data)
            # Generate stats if requested for a single file
            if generate_stats and stats_data:
                generate_stats_file(stats_data, os.path.dirname(path))
    elif mode == 'directory':
        process_directory(path, cutoff_len, sRg_cutoff,
                         linear_eig_ratio_cutoff, linear_step_align_cutoff,
                         method, include_shape_metrics, include_linear_metrics,
                         suffix, split_outputs, mobile_only, output_dir,
                         generate_stats)
    else:
        print(f"Invalid mode: {mode}. Use 'file' or 'directory'.")


def main():
    # Check if script is run directly in Spyder/IDE
    if USE_DIRECT_EXECUTION:
        print("Running with direct execution settings from CONFIG section")
        run_script(EXECUTION_MODE,
                  FILE_PATH if EXECUTION_MODE == 'file' else DIRECTORY_PATH,
                  CUTOFF_LEN,
                  SRG_CUTOFF,
                  LINEAR_EIGENVALUE_RATIO_CUTOFF,
                  LINEAR_STEP_ALIGNMENT_CUTOFF,
                  RG_METHOD,
                  INCLUDE_SHAPE_METRICS,
                  INCLUDE_LINEAR_METRICS,
                  OUTPUT_SUFFIX,
                  SPLIT_OUTPUTS,
                  MOBILE_ONLY,
                  OUTPUT_DIR,
                  GENERATE_STATS)
        return

    # Otherwise, parse command line arguments
    parser = argparse.ArgumentParser(description="Calculate trajectory metrics")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', help="Path to a CSV file")
    group.add_argument('--directory', help="Path to a directory of CSV files")

    parser.add_argument('--cutoff-len', type=int, default=3,
                        help="Minimum trajectory length (default: 3)")
    parser.add_argument('--srg-cutoff', type=float, default=2.22236433588659,
                        help="sRg threshold for mobile/immobile classification (default: 2.22236433588659)")
    parser.add_argument('--linear-eigenvalue-ratio', type=float, default=5.0,
                        help="Eigenvalue ratio threshold for linear classification (default: 5.0)")
    parser.add_argument('--linear-step-alignment', type=float, default=0.7,
                        help="Step alignment threshold for linear classification (default: 0.7)")
    parser.add_argument('--method', choices=['simple', 'tensor'], default='tensor',
                        help="Method to calculate Rg (default: tensor)")
    parser.add_argument('--include-shape-metrics', action='store_true', default=True,
                        help="Include shape metrics (asymmetry, skewness, kurtosis) in output")
    parser.add_argument('--no-shape-metrics', action='store_false', dest='include_shape_metrics',
                        help="Do not include shape metrics in output")
    parser.add_argument('--include-linear-metrics', action='store_true', default=True,
                        help="Include linear motion metrics in output")
    parser.add_argument('--no-linear-metrics', action='store_false', dest='include_linear_metrics',
                        help="Do not include linear motion metrics in output")
    parser.add_argument('--suffix', default='_metrics',
                        help="Suffix for output filenames (default: _metrics)")
    parser.add_argument('--split-outputs', action='store_true', default=False,
                        help="Create separate files for different classifications")
    parser.add_argument('--mobile-only', action='store_true', default=False,
                        help="Only include mobile tracks in split outputs")
    parser.add_argument('--output-dir',
                        help="Directory for output files (default: same as input)")
    parser.add_argument('--generate-stats', action='store_true', default=False,
                    help="Generate statistics summary file")


    args = parser.parse_args()

    if args.file:
        df = process_csv_file(args.file, args.cutoff_len, args.srg_cutoff,
                             args.linear_eigenvalue_ratio, args.linear_step_alignment,
                             args.method, args.include_shape_metrics, args.include_linear_metrics)
        if df is not None:
            save_processed_data(df, args.file, args.suffix, args.split_outputs,
                               args.mobile_only, args.output_dir)
    elif args.directory:
        process_directory(args.directory, args.cutoff_len, args.srg_cutoff,
                        args.linear_eigenvalue_ratio, args.linear_step_alignment,
                        args.method, args.include_shape_metrics, args.include_linear_metrics,
                        args.suffix, args.split_outputs, args.mobile_only, args.output_dir,
                        args.generate_stats)


if __name__ == "__main__":
    main()
