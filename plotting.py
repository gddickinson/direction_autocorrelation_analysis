"""
Plotting functions for autocorrelation analysis.

All visualization logic: autocorrelation plots, individual track overlays,
condition summaries, and cross-condition comparisons.
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import random
from typing import Dict, Optional, Tuple

from config import PLOT_Y_MIN, PLOT_Y_MAX


def create_autocorrel_plot(all_results: dict, output_dir: str,
                            output_prefix: str = "",
                            title: str = "Autocorrelation Analysis") -> None:
    """
    Create a plot of autocorrelation results for one or more conditions.

    Args:
        all_results: Dict mapping condition names to averages DataFrames.
        output_dir: Directory to save plots.
        output_prefix: Optional prefix for filenames.
        title: Plot title.
    """
    print("Creating autocorrelation plot...")
    plt.figure(figsize=(12, 8))

    markers = ['o', 's', '^', 'd', 'v', '<', '>', 'p', '*']
    colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k']

    for i, (condition, results) in enumerate(all_results.items()):
        x = np.array([float(col) for col in results.columns])
        y = results.loc['AVG'].values
        yerr = results.loc['SEM'].values

        marker = markers[i % len(markers)]
        color = colors[i % len(colors)]

        plt.errorbar(x, y, yerr=yerr, fmt=f'{marker}-', capsize=5,
                     color=color, linewidth=2, label=condition, markersize=8)

    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title(title, fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)
    plt.xlim(0, max([max([float(col) for col in results.columns]) for results in all_results.values()]) * 1.05)

    if len(all_results) > 1:
        plt.legend()

    plt.tight_layout()

    plot_name = f"{output_prefix}autocorrelation_plot" if output_prefix else "autocorrelation_plot"
    png_path = os.path.join(output_dir, f"{plot_name}.png")
    pdf_path = os.path.join(output_dir, f"{plot_name}.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    print(f"Saved plot to {png_path}")
    plt.close()


def plot_individual_tracks(tracks_df: pd.DataFrame, averages: pd.DataFrame,
                            output_dir: str, sheet_name: str,
                            output_prefix: str = "",
                            max_tracks: int = 100) -> Tuple[str, str]:
    """
    Create a plot showing individual tracks alongside the average.

    Args:
        tracks_df: DataFrame with individual track results.
        averages: DataFrame with average results.
        output_dir: Directory to save the plot.
        sheet_name: Name of the sheet/condition.
        output_prefix: Prefix for output filenames.
        max_tracks: Maximum number of tracks to plot.

    Returns:
        Tuple of (png_path, pdf_path).
    """
    print(f"  Creating individual tracks plot for {sheet_name}...")

    plt.figure(figsize=(12, 8))

    unique_tracks = tracks_df['track_id'].unique()
    tracks_to_plot = unique_tracks
    if len(unique_tracks) > max_tracks:
        print(f"  Sampling {max_tracks} tracks out of {len(unique_tracks)} for visualization")
        tracks_to_plot = random.sample(list(unique_tracks), max_tracks)

    pivot_df = tracks_df.pivot(index='track_id', columns='time_interval', values='correlation')
    pivot_df[0] = 1.0
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)

    for track_id in tracks_to_plot:
        if track_id in pivot_df.index:
            track_data = pivot_df.loc[track_id]
            plt.plot(track_data.index, track_data.values, '-', color='gray', alpha=0.1, linewidth=0.5)

    x = np.array([float(col) for col in averages.columns])
    y = averages.loc['AVG'].values
    yerr = averages.loc['SEM'].values

    plt.errorbar(x, y, yerr=yerr, fmt='o-', color='blue', linewidth=2,
                 label='Average', markersize=6, capsize=5)

    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title(f'{sheet_name} - Individual Tracks and Average', fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)
    plt.xlim(0, max(x) * 1.05)
    plt.legend(['Individual Tracks', 'Average (+/- SEM)'])
    plt.tight_layout()

    base_name = f"{output_prefix}{sheet_name}_individual_tracks_plot" if output_prefix else f"{sheet_name}_individual_tracks_plot"
    png_path = os.path.join(output_dir, f"{base_name}.png")
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    print(f"  Saved individual tracks plot to {png_path}")
    plt.close()

    return png_path, pdf_path


def create_condition_plot(summary_df: pd.DataFrame, output_dir: str,
                           condition_name: str) -> Tuple[str, str]:
    """
    Create a plot for a condition showing average autocorrelation and SEM.

    Args:
        summary_df: DataFrame with summary statistics.
        output_dir: Directory to save the plot.
        condition_name: Name of the condition.

    Returns:
        Tuple of (png_path, pdf_path).
    """
    print(f"Creating plot for condition: {condition_name}")

    plt.figure(figsize=(12, 8))

    x = np.array([float(col) for col in summary_df.columns])
    y = summary_df.loc['AVG'].values
    yerr = summary_df.loc['SEM'].values

    plt.errorbar(x, y, yerr=yerr, fmt='o-', capsize=5,
                 color='b', linewidth=2, markersize=8)

    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title(f'{condition_name} Autocorrelation', fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)
    plt.xlim(0, max(x) * 1.05)
    plt.tight_layout()

    png_path = os.path.join(output_dir, f"{condition_name}_summary_plot.png")
    pdf_path = os.path.join(output_dir, f"{condition_name}_summary_plot.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    print(f"Saved condition plot to {png_path}")
    plt.close()

    return png_path, pdf_path


def create_condition_individual_tracks_plot(aggregated_tracks_df: pd.DataFrame,
                                            summary_df: pd.DataFrame,
                                            output_dir: str,
                                            condition_name: str,
                                            max_tracks: int = 100) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a plot showing individual tracks from all files in a condition.

    Args:
        aggregated_tracks_df: DataFrame with all individual track results.
        summary_df: DataFrame with condition summary statistics.
        output_dir: Directory to save the plot.
        condition_name: Name of the condition.
        max_tracks: Maximum number of tracks to plot.

    Returns:
        Tuple of (png_path, pdf_path) or (None, None).
    """
    if aggregated_tracks_df is None or len(aggregated_tracks_df) == 0:
        print(f"  No individual track data available for condition: {condition_name}")
        return None, None

    print(f"Creating individual tracks plot for condition: {condition_name}")

    plt.figure(figsize=(12, 8))

    unique_tracks = aggregated_tracks_df['track_id'].unique()
    tracks_to_plot = unique_tracks
    if len(unique_tracks) > max_tracks:
        print(f"  Sampling {max_tracks} tracks out of {len(unique_tracks)} for visualization")
        tracks_to_plot = random.sample(list(unique_tracks), max_tracks)

    pivot_df = aggregated_tracks_df.pivot(index='track_id', columns='time_interval', values='correlation')
    pivot_df[0] = 1.0
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)

    for track_id in tracks_to_plot:
        if track_id in pivot_df.index:
            track_data = pivot_df.loc[track_id]
            plt.plot(track_data.index, track_data.values, '-', color='gray', alpha=0.1, linewidth=0.5)

    x = np.array([float(col) for col in summary_df.columns])
    y = summary_df.loc['AVG'].values
    yerr = summary_df.loc['SEM'].values

    plt.errorbar(x, y, yerr=yerr, fmt='o-', color='blue', linewidth=2,
                 label='Average', markersize=6, capsize=5)

    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title(f'{condition_name} - Individual Tracks and Average', fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)
    plt.xlim(0, max(x) * 1.05)
    plt.legend(['Individual Tracks', 'Average (+/- SEM)'])
    plt.tight_layout()

    png_path = os.path.join(output_dir, f"{condition_name}_all_tracks_plot.png")
    pdf_path = os.path.join(output_dir, f"{condition_name}_all_tracks_plot.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    print(f"Saved condition individual tracks plot to {png_path}")
    plt.close()

    return png_path, pdf_path


def create_cross_condition_plot(condition_summaries: dict,
                                 main_output_dir: str) -> Tuple[str, str]:
    """
    Create a comparison plot across all conditions.

    Args:
        condition_summaries: Dict mapping condition names to summary DataFrames.
        main_output_dir: Directory to save the plot.

    Returns:
        Tuple of (png_path, pdf_path).
    """
    print("\nCreating cross-condition comparison plot...")

    plt.figure(figsize=(12, 8))

    markers = ['o', 's', '^', 'd', 'v', '<', '>', 'p', '*']
    colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k']

    for i, (condition, summary) in enumerate(condition_summaries.items()):
        x = np.array([float(col) for col in summary.columns])
        y = summary.loc['AVG'].values
        yerr = summary.loc['SEM'].values

        marker = markers[i % len(markers)]
        color = colors[i % len(colors)]

        plt.errorbar(x, y, yerr=yerr, fmt=f'{marker}-', capsize=5,
                     color=color, linewidth=2, label=condition, markersize=8)

    plt.grid(False)
    plt.xlabel('Time Interval', fontsize=14)
    plt.ylabel('Direction Autocorrelation', fontsize=14)
    plt.title('Comparison Across Conditions', fontsize=16)
    plt.ylim(PLOT_Y_MIN, PLOT_Y_MAX)

    max_x = max([max([float(col) for col in summary.columns]) for summary in condition_summaries.values()])
    plt.xlim(0, max_x * 1.05)
    plt.legend()
    plt.tight_layout()

    png_path = os.path.join(main_output_dir, "condition_comparison_plot.png")
    pdf_path = os.path.join(main_output_dir, "condition_comparison_plot.pdf")

    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    print(f"Saved cross-condition comparison plot to {png_path}")
    plt.close()

    return png_path, pdf_path
