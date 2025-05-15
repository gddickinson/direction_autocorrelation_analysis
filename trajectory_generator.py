#!/usr/bin/env python3
"""
trajectory_generator.py - Generate test trajectories and analyze their metrics

This script generates synthetic particle trajectories for different motion types:
- Linear unidirectional motion
- Linear bidirectional (back-and-forth) motion
- Random diffusion (Brownian motion)
- Confined diffusion (Brownian within boundaries)
- Directed random motion (Brownian with drift)

It analyzes these trajectories using the trajectory_analyzer functions and
creates visualizations to help determine optimal threshold values.

Usage:
  python trajectory_generator.py

Output:
  - CSV files for each motion type
  - Trajectory plots
  - Metric distribution plots
  - Threshold analysis
  - Summary report
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.metrics import roc_curve, auc
from scipy import stats
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d import Axes3D

# Import functions from trajectory_analyzer
# Note: Ensure trajectory_analyzer.py is in the same directory
from trajectory_analyzer import (
    get_trajectory_metrics_tensor, get_radius_of_gyration_simple,
    get_mean_step_length, get_scaled_rg, classify_linear_motion
)

#######################################################################
# CONFIG SECTION
#######################################################################
# Output directory
OUTPUT_DIR = "trajectory_test_data"

# Number of trajectories to generate per motion type
N_TRAJECTORIES = 50

# Number of points per trajectory
N_POINTS = 100

# Random seed for reproducibility
RANDOM_SEED = 42

# Parameters for trajectory generation
TRAJECTORY_PARAMS = {
    'linear_unidirectional': {
        'step_size': 1.0,
        'noise_level': 0.1,  # Perpendicular noise
    },
    'linear_bidirectional': {
        'step_size': 1.0,
        'noise_level': 0.1,
        'oscillation_period': 20,  # Points per oscillation
    },
    'random_diffusion': {
        'step_size': 1.0,
    },
    'confined_diffusion': {
        'step_size': 1.0,
        'confinement_radius': 10.0,
    },
    'directed_random': {
        'step_size': 1.0,
        'drift_magnitude': 0.5,
    }
}

# Linear motion classification thresholds to test
EIGENVALUE_RATIO_THRESHOLDS = np.linspace(2, 10, 9)
STEP_ALIGNMENT_THRESHOLDS = np.linspace(0.5, 0.9, 9)
DIRECTIONALITY_RATIO_THRESHOLDS = np.linspace(0.4, 0.9, 6)

# Default threshold values
DEFAULT_EIGENVALUE_RATIO_THRESHOLD = 5.0
DEFAULT_STEP_ALIGNMENT_THRESHOLD = 0.7
DEFAULT_DIRECTIONALITY_THRESHOLD = 0.7

# Plot settings
PLOT_DPI = 150
PLOT_FIGSIZE = (12, 10)
COLORS = {
    'linear_unidirectional': '#1f77b4',  # blue
    'linear_bidirectional': '#ff7f0e',   # orange
    'random_diffusion': '#2ca02c',       # green
    'confined_diffusion': '#d62728',     # red
    'directed_random': '#9467bd',        # purple
}
MARKERS = {
    'linear_unidirectional': 'o',
    'linear_bidirectional': 's',
    'random_diffusion': '^',
    'confined_diffusion': 'D',
    'directed_random': 'X',
}
#######################################################################


def generate_linear_unidirectional(n_points, step_size=1.0, noise_level=0.1, angle=None):
    """Generate a linear unidirectional trajectory with perpendicular noise.

    Args:
        n_points: Number of points in the trajectory
        step_size: Size of each step
        noise_level: Standard deviation of perpendicular noise
        angle: Direction angle in radians (random if None)

    Returns:
        Nx2 array of trajectory coordinates
    """
    # Random angle if not specified
    if angle is None:
        angle = np.random.uniform(0, 2 * np.pi)

    # Direction vector
    direction = np.array([np.cos(angle), np.sin(angle)])

    # Generate steps with noise perpendicular to direction
    steps = np.zeros((n_points, 2))

    for i in range(1, n_points):
        # Perpendicular vector
        perp_vector = np.array([-direction[1], direction[0]])

        # Add noise perpendicular to direction
        perpendicular_noise = np.random.normal(0, noise_level) * perp_vector

        # Create step
        steps[i] = step_size * direction + perpendicular_noise

    # Accumulate steps to get trajectory
    trajectory = np.cumsum(steps, axis=0)

    return trajectory


def generate_linear_bidirectional(n_points, step_size=1.0, noise_level=0.1, oscillation_period=20, angle=None):
    """Generate a linear bidirectional (oscillating) trajectory.

    Args:
        n_points: Number of points in the trajectory
        step_size: Size of each step
        noise_level: Standard deviation of perpendicular noise
        oscillation_period: Points per complete oscillation
        angle: Direction angle in radians (random if None)

    Returns:
        Nx2 array of trajectory coordinates
    """
    # Random angle if not specified
    if angle is None:
        angle = np.random.uniform(0, 2 * np.pi)

    # Direction vector
    direction = np.array([np.cos(angle), np.sin(angle)])

    # Perpendicular vector
    perp_vector = np.array([-direction[1], direction[0]])

    # Generate oscillating movement along the direction
    steps = np.zeros((n_points, 2))

    for i in range(1, n_points):
        # Oscillating direction - cosine function controls direction reversal
        direction_factor = np.cos(2 * np.pi * i / oscillation_period)

        # Perpendicular noise
        perpendicular_noise = np.random.normal(0, noise_level) * perp_vector

        # Create step
        steps[i] = step_size * direction_factor * direction + perpendicular_noise

    # Accumulate steps to get trajectory
    trajectory = np.cumsum(steps, axis=0)

    return trajectory


def generate_random_diffusion(n_points, step_size=1.0):
    """Generate a random diffusion (Brownian motion) trajectory.

    Args:
        n_points: Number of points in the trajectory
        step_size: Average size of each step

    Returns:
        Nx2 array of trajectory coordinates
    """
    # Generate random steps
    steps = np.random.normal(0, step_size, (n_points, 2))

    # Set first step to zero
    steps[0] = [0, 0]

    # Accumulate steps to get trajectory
    trajectory = np.cumsum(steps, axis=0)

    return trajectory


def generate_confined_diffusion(n_points, step_size=1.0, confinement_radius=10.0):
    """Generate a confined diffusion trajectory (Brownian motion within boundaries).

    Args:
        n_points: Number of points in the trajectory
        step_size: Average size of each step
        confinement_radius: Radius of the confinement region

    Returns:
        Nx2 array of trajectory coordinates
    """
    trajectory = np.zeros((n_points, 2))

    for i in range(1, n_points):
        # Generate random step
        step = np.random.normal(0, step_size, 2)

        # Proposed new position
        proposed_position = trajectory[i-1] + step

        # Calculate distance from origin
        distance = np.sqrt(np.sum(proposed_position**2))

        # If outside confinement, reflect back
        if distance > confinement_radius:
            # Vector from origin to proposed position
            direction = proposed_position / distance

            # Reflection point on the boundary
            reflection_point = confinement_radius * direction

            # Reflect the excess distance back inside
            excess_distance = distance - confinement_radius

            # New position after reflection
            trajectory[i] = reflection_point - excess_distance * direction
        else:
            # Accept the step if inside confinement
            trajectory[i] = proposed_position

    return trajectory


def generate_directed_random(n_points, step_size=1.0, drift_magnitude=0.5, drift_angle=None):
    """Generate a directed random motion trajectory (Brownian motion with drift).

    Args:
        n_points: Number of points in the trajectory
        step_size: Average size of each random step
        drift_magnitude: Magnitude of the drift vector
        drift_angle: Direction angle of drift in radians (random if None)

    Returns:
        Nx2 array of trajectory coordinates
    """
    # Random drift angle if not specified
    if drift_angle is None:
        drift_angle = np.random.uniform(0, 2 * np.pi)

    # Drift vector
    drift_vector = drift_magnitude * np.array([np.cos(drift_angle), np.sin(drift_angle)])

    # Generate steps with drift
    steps = np.random.normal(0, step_size, (n_points, 2))

    # Add drift to each step
    steps += drift_vector

    # Set first step to zero
    steps[0] = [0, 0]

    # Accumulate steps to get trajectory
    trajectory = np.cumsum(steps, axis=0)

    return trajectory


def generate_trajectories(n_trajectories=50, n_points=100):
    """Generate trajectories for all motion types.

    Args:
        n_trajectories: Number of trajectories per motion type
        n_points: Number of points per trajectory

    Returns:
        Dictionary with motion types as keys and lists of trajectories as values
    """
    # Set random seed for reproducibility
    np.random.seed(RANDOM_SEED)

    trajectories = {}

    # Linear unidirectional
    trajectories['linear_unidirectional'] = []
    for i in range(n_trajectories):
        params = TRAJECTORY_PARAMS['linear_unidirectional']
        traj = generate_linear_unidirectional(
            n_points,
            step_size=params['step_size'],
            noise_level=params['noise_level']
        )
        trajectories['linear_unidirectional'].append(traj)

    # Linear bidirectional
    trajectories['linear_bidirectional'] = []
    for i in range(n_trajectories):
        params = TRAJECTORY_PARAMS['linear_bidirectional']
        traj = generate_linear_bidirectional(
            n_points,
            step_size=params['step_size'],
            noise_level=params['noise_level'],
            oscillation_period=params['oscillation_period']
        )
        trajectories['linear_bidirectional'].append(traj)

    # Random diffusion
    trajectories['random_diffusion'] = []
    for i in range(n_trajectories):
        params = TRAJECTORY_PARAMS['random_diffusion']
        traj = generate_random_diffusion(
            n_points,
            step_size=params['step_size']
        )
        trajectories['random_diffusion'].append(traj)

    # Confined diffusion
    trajectories['confined_diffusion'] = []
    for i in range(n_trajectories):
        params = TRAJECTORY_PARAMS['confined_diffusion']
        traj = generate_confined_diffusion(
            n_points,
            step_size=params['step_size'],
            confinement_radius=params['confinement_radius']
        )
        trajectories['confined_diffusion'].append(traj)

    # Directed random
    trajectories['directed_random'] = []
    for i in range(n_trajectories):
        params = TRAJECTORY_PARAMS['directed_random']
        traj = generate_directed_random(
            n_points,
            step_size=params['step_size'],
            drift_magnitude=params['drift_magnitude']
        )
        trajectories['directed_random'].append(traj)

    return trajectories


def trajectories_to_dataframe(trajectories):
    """Convert trajectories dictionary to DataFrames for each motion type.

    Args:
        trajectories: Dictionary with motion types as keys and lists of trajectories as values

    Returns:
        Dictionary with motion types as keys and DataFrames as values
    """
    dataframes = {}

    for motion_type, trajs in trajectories.items():
        # Create a list to store all trajectory data
        all_data = []

        for i, traj in enumerate(trajs):
            # Create DataFrame for this trajectory
            df = pd.DataFrame(traj, columns=['x', 'y'])
            df['track_number'] = i + 1
            df['frame'] = np.arange(len(traj))
            df['motion_type'] = motion_type

            # Add to list
            all_data.append(df)

        # Concatenate all trajectories for this motion type
        dataframes[motion_type] = pd.concat(all_data, ignore_index=True)

    return dataframes


def save_trajectories_to_csv(dataframes, output_dir):
    """Save trajectory DataFrames to CSV files.

    Args:
        dataframes: Dictionary with motion types as keys and DataFrames as values
        output_dir: Directory to save the CSV files
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Save each motion type to a CSV file
    for motion_type, df in dataframes.items():
        file_path = os.path.join(output_dir, f"{motion_type}_trajectories.csv")
        df.to_csv(file_path, index=False)
        print(f"Saved {motion_type} trajectories to {file_path}")

    # Create a combined CSV with all trajectories
    combined_df = pd.concat(dataframes.values(), ignore_index=True)
    combined_file_path = os.path.join(output_dir, "all_trajectories.csv")
    combined_df.to_csv(combined_file_path, index=False)
    print(f"Saved combined trajectories to {combined_file_path}")

    return combined_df


def calculate_metrics_for_trajectory(trajectory, track_number, motion_type):
    """Calculate metrics for a single trajectory.

    Args:
        trajectory: Nx2 array of trajectory coordinates
        track_number: Trajectory identifier
        motion_type: Type of motion (for grouping)

    Returns:
        Dictionary with calculated metrics
    """
    # Calculate tensor metrics
    tensor_metrics = get_trajectory_metrics_tensor(trajectory)

    # Calculate simple Rg
    simple_rg = get_radius_of_gyration_simple(trajectory)

    # Calculate mean step length
    mean_step = get_mean_step_length(trajectory)

    # Calculate sRg
    srg_tensor = get_scaled_rg(tensor_metrics['rg'], mean_step)
    srg_simple = get_scaled_rg(simple_rg, mean_step)

    # Classify linearity with default thresholds
    linear_classification = classify_linear_motion(
        tensor_metrics['eigenvalue_ratio'],
        tensor_metrics['step_alignment'],
        tensor_metrics['directionality_ratio']
    )

    # Create metrics dictionary
    metrics = {
        'track_number': track_number,
        'motion_type': motion_type,
        'rg_tensor': tensor_metrics['rg'],
        'rg_simple': simple_rg,
        'mean_step_length': mean_step,
        'sRg_tensor': srg_tensor,
        'sRg_simple': srg_simple,
        'asymmetry': tensor_metrics['asymmetry'],
        'skewness': tensor_metrics['skewness'],
        'kurtosis': tensor_metrics['kurtosis'],
        'eigenvalue_ratio': tensor_metrics['eigenvalue_ratio'],
        'step_alignment': tensor_metrics['step_alignment'],
        'directionality_ratio': tensor_metrics['directionality_ratio'],
        'linear_classification': linear_classification,
        'num_points': len(trajectory)
    }

    return metrics


def calculate_metrics_for_all_trajectories(trajectories):
    """Calculate metrics for all trajectories.

    Args:
        trajectories: Dictionary with motion types as keys and lists of trajectories as values

    Returns:
        DataFrame with calculated metrics for all trajectories
    """
    # Create a list to store all metrics
    all_metrics = []

    for motion_type, trajs in trajectories.items():
        for i, traj in enumerate(trajs):
            # Calculate metrics for this trajectory
            metrics = calculate_metrics_for_trajectory(traj, i + 1, motion_type)

            # Add to list
            all_metrics.append(metrics)

    # Convert to DataFrame
    metrics_df = pd.DataFrame(all_metrics)

    return metrics_df


def create_trajectory_plots(trajectories, output_dir):
    """Create plots of example trajectories for each motion type.

    Args:
        trajectories: Dictionary with motion types as keys and lists of trajectories as values
        output_dir: Directory to save the plots
    """
    # Create output directory if it doesn't exist
    plot_dir = os.path.join(output_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    # Create a figure with subplots for each motion type
    fig, axs = plt.subplots(2, 3, figsize=PLOT_FIGSIZE, dpi=PLOT_DPI)
    axs = axs.flatten()

    # Plot one example trajectory for each motion type
    for i, (motion_type, trajs) in enumerate(trajectories.items()):
        # Select first trajectory
        traj = trajs[0]

        # Plot trajectory
        axs[i].plot(traj[:, 0], traj[:, 1], '-o', markersize=4,
                   color=COLORS[motion_type],
                   label=motion_type.replace('_', ' ').title())

        # Mark start and end points
        axs[i].plot(traj[0, 0], traj[0, 1], 'go', markersize=8, label='Start')
        axs[i].plot(traj[-1, 0], traj[-1, 1], 'ro', markersize=8, label='End')

        # Set title and labels
        axs[i].set_title(motion_type.replace('_', ' ').title())
        axs[i].set_xlabel('X')
        axs[i].set_ylabel('Y')
        axs[i].grid(True, alpha=0.3)

        # Only show legend for first plot
        if i == 0:
            axs[i].legend()

    # Remove empty subplot if any
    if len(trajectories) < len(axs):
        fig.delaxes(axs[-1])

    # Adjust layout
    plt.tight_layout()

    # Save figure
    plt.savefig(os.path.join(plot_dir, "example_trajectories.png"))
    plt.close()

    # Now create a combined plot with multiple trajectories per motion type
    plt.figure(figsize=PLOT_FIGSIZE, dpi=PLOT_DPI)

    # Plot 5 trajectories for each motion type
    for motion_type, trajs in trajectories.items():
        for j, traj in enumerate(trajs[:5]):  # Plot first 5 trajectories
            # Add small offset to avoid overlap
            offset = np.array([j * 5, j * 5])
            plt.plot(traj[:, 0] + offset[0], traj[:, 1] + offset[1], '-',
                    color=COLORS[motion_type], linewidth=1, alpha=0.7)

    # Create custom legend
    legend_elements = [
        Patch(facecolor=COLORS[motion_type], label=motion_type.replace('_', ' ').title())
        for motion_type in trajectories.keys()
    ]
    plt.legend(handles=legend_elements, loc='best')

    # Set title and labels
    plt.title('Multiple Trajectories by Motion Type')
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.grid(True, alpha=0.3)

    # Save figure
    plt.savefig(os.path.join(plot_dir, "multiple_trajectories.png"))
    plt.close()

    # Create 3D plot of metric space
    fig = plt.figure(figsize=PLOT_FIGSIZE, dpi=PLOT_DPI)
    ax = fig.add_subplot(111, projection='3d')

    # Calculate metrics for trajectories
    metrics_df = calculate_metrics_for_all_trajectories(trajectories)

    # Plot points in 3D space of eigenvalue_ratio, step_alignment, and directionality_ratio
    for motion_type in trajectories.keys():
        df_subset = metrics_df[metrics_df['motion_type'] == motion_type]
        ax.scatter(
            df_subset['eigenvalue_ratio'],
            df_subset['step_alignment'],
            df_subset['directionality_ratio'],
            color=COLORS[motion_type],
            marker=MARKERS[motion_type],
            label=motion_type.replace('_', ' ').title(),
            alpha=0.7
        )

    # Set title and labels
    ax.set_title('3D Metric Space for Motion Classification')
    ax.set_xlabel('Eigenvalue Ratio')
    ax.set_ylabel('Step Alignment')
    ax.set_zlabel('Directionality Ratio')
    ax.legend()

    # Save figure
    plt.savefig(os.path.join(plot_dir, "metric_space_3d.png"))
    plt.close()


def create_metric_distribution_plots(metrics_df, output_dir):
    """Create distribution plots for key metrics.

    Args:
        metrics_df: DataFrame with calculated metrics
        output_dir: Directory to save the plots
    """
    # Create output directory if it doesn't exist
    plot_dir = os.path.join(output_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    # List of metrics to plot
    metrics_to_plot = [
        'eigenvalue_ratio', 'step_alignment', 'directionality_ratio',
        'asymmetry', 'skewness', 'kurtosis',
        'sRg_tensor', 'sRg_simple'
    ]

    # Create distribution plots for each metric
    for metric in metrics_to_plot:
        plt.figure(figsize=(10, 6), dpi=PLOT_DPI)

        # Create violin plots
        sns.violinplot(
            x='motion_type',
            y=metric,
            data=metrics_df,
            palette=COLORS,
            inner='quartile'
        )

        # Add individual points
        sns.stripplot(
            x='motion_type',
            y=metric,
            data=metrics_df,
            color='black',
            alpha=0.4,
            size=3,
            jitter=True
        )

        # Rotate x-axis labels
        plt.xticks(rotation=45, ha='right')

        # Set title and labels
        plt.title(f'Distribution of {metric}')
        plt.xlabel('Motion Type')
        plt.ylabel(metric)
        plt.tight_layout()

        # Save figure
        plt.savefig(os.path.join(plot_dir, f"{metric}_distribution.png"))
        plt.close()

    # Create pairplot for key metrics
    key_metrics = ['eigenvalue_ratio', 'step_alignment', 'directionality_ratio']
    plt.figure(figsize=PLOT_FIGSIZE, dpi=PLOT_DPI)

    # Create pairplot matrix
    g = sns.pairplot(
        metrics_df,
        vars=key_metrics,
        hue='motion_type',
        palette=COLORS,
        diag_kind='kde',
        markers=[MARKERS[mt] for mt in metrics_df['motion_type'].unique()],
        height=3
    )

    # Set title
    g.fig.suptitle('Pairplot of Key Metrics for Motion Classification', y=1.02)

    # Save figure
    plt.savefig(os.path.join(plot_dir, "metric_pairplot.png"))
    plt.close()


def analyze_classification_performance(metrics_df, output_dir):
    """Analyze the performance of classification thresholds.

    Args:
        metrics_df: DataFrame with calculated metrics
        output_dir: Directory to save the analysis
    """
    # Create output directory if it doesn't exist
    plot_dir = os.path.join(output_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    # Create binary truth labels
    metrics_df['is_linear'] = metrics_df['motion_type'].isin(['linear_unidirectional', 'linear_bidirectional'])
    metrics_df['is_unidirectional'] = metrics_df['motion_type'] == 'linear_unidirectional'

    # Create a figure for ROC curves
    plt.figure(figsize=PLOT_FIGSIZE, dpi=PLOT_DPI)

    # Calculate ROC curve for eigenvalue ratio (linear vs non-linear)
    fpr, tpr, thresholds = roc_curve(metrics_df['is_linear'], metrics_df['eigenvalue_ratio'])
    roc_auc = auc(fpr, tpr)

    # Plot ROC curve
    plt.plot(fpr, tpr, label=f'Eigenvalue Ratio (AUC = {roc_auc:.3f})')

    # Calculate ROC curve for step alignment (linear vs non-linear)
    fpr, tpr, thresholds = roc_curve(metrics_df['is_linear'], metrics_df['step_alignment'])
    roc_auc = auc(fpr, tpr)

    # Plot ROC curve
    plt.plot(fpr, tpr, label=f'Step Alignment (AUC = {roc_auc:.3f})')

    # Calculate ROC curve for combined score
    combined_score = metrics_df['eigenvalue_ratio'] * metrics_df['step_alignment']
    fpr, tpr, thresholds = roc_curve(metrics_df['is_linear'], combined_score)
    roc_auc = auc(fpr, tpr)

    # Plot ROC curve
    plt.plot(fpr, tpr, label=f'Combined Score (AUC = {roc_auc:.3f})')

    # Plot diagonal line
    plt.plot([0, 1], [0, 1], 'k--')

    # Set title and labels
    plt.title('ROC Curve for Linear vs Non-Linear Classification')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.legend(loc='lower right')
    plt.grid(True, alpha=0.3)

    # Save figure
    plt.savefig(os.path.join(plot_dir, "roc_curve_linear.png"))
    plt.close()

    # Create a similar plot for unidirectional vs bidirectional classification
    linear_df = metrics_df[metrics_df['is_linear']]

    # Only proceed if we have enough data
    if len(linear_df) > 0 and len(linear_df['is_unidirectional'].unique()) > 1:
        plt.figure(figsize=PLOT_FIGSIZE, dpi=PLOT_DPI)

        # Calculate ROC curve for directionality ratio
        fpr, tpr, thresholds = roc_curve(linear_df['is_unidirectional'], linear_df['directionality_ratio'])
        roc_auc = auc(fpr, tpr)

        # Plot ROC curve
        plt.plot(fpr, tpr, label=f'Directionality Ratio (AUC = {roc_auc:.3f})')

        # Plot diagonal line
        plt.plot([0, 1], [0, 1], 'k--')

        # Set title and labels
        plt.title('ROC Curve for Unidirectional vs Bidirectional Classification')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.legend(loc='lower right')
        plt.grid(True, alpha=0.3)

        # Save figure
        plt.savefig(os.path.join(plot_dir, "roc_curve_directionality.png"))
        plt.close()

    # Create threshold performance plots
    # For linear vs non-linear classification
    performance_data = []

    # Test different combinations of thresholds
    for er_thresh in EIGENVALUE_RATIO_THRESHOLDS:
        for sa_thresh in STEP_ALIGNMENT_THRESHOLDS:
            # Apply classification
            predicted_linear = (metrics_df['eigenvalue_ratio'] >= er_thresh) & (metrics_df['step_alignment'] >= sa_thresh)

            # Calculate performance metrics
            true_positive = np.sum(predicted_linear & metrics_df['is_linear'])
            false_positive = np.sum(predicted_linear & ~metrics_df['is_linear'])
            true_negative = np.sum(~predicted_linear & ~metrics_df['is_linear'])
            false_negative = np.sum(~predicted_linear & metrics_df['is_linear'])

            # Calculate accuracy, precision, recall, and F1 score
            total = len(metrics_df)
            accuracy = (true_positive + true_negative) / total
            precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0
            recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            # Add to performance data
            performance_data.append({
                'eigenvalue_ratio_threshold': er_thresh,
                'step_alignment_threshold': sa_thresh,
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1
            })

    # Convert to DataFrame
    performance_df = pd.DataFrame(performance_data)

    # Create heatmap of F1 scores
    plt.figure(figsize=PLOT_FIGSIZE, dpi=PLOT_DPI)

    # Reshape data for heatmap
    heatmap_data = performance_df.pivot_table(
        index='eigenvalue_ratio_threshold',
        columns='step_alignment_threshold',
        values='f1_score'
    )

    # Create heatmap
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt='.2f',
        cmap='viridis',
        vmin=0,
        vmax=1
    )

    # Set title and labels
    plt.title('F1 Score for Different Threshold Combinations')
    plt.xlabel('Step Alignment Threshold')
    plt.ylabel('Eigenvalue Ratio Threshold')

    # Save figure
    plt.savefig(os.path.join(plot_dir, "threshold_heatmap.png"))
    plt.close()

    # Find optimal thresholds
    best_idx = performance_df['f1_score'].idxmax()
    best_er_thresh = performance_df.loc[best_idx, 'eigenvalue_ratio_threshold']
    best_sa_thresh = performance_df.loc[best_idx, 'step_alignment_threshold']
    best_f1 = performance_df.loc[best_idx, 'f1_score']

    # Create summary of results
    summary = {
        'optimal_eigenvalue_ratio_threshold': best_er_thresh,
        'optimal_step_alignment_threshold': best_sa_thresh,
        'optimal_f1_score': best_f1,
        'default_eigenvalue_ratio_threshold': DEFAULT_EIGENVALUE_RATIO_THRESHOLD,
        'default_step_alignment_threshold': DEFAULT_STEP_ALIGNMENT_THRESHOLD,
        'default_directionality_threshold': DEFAULT_DIRECTIONALITY_THRESHOLD
    }

    # Add performance with default thresholds
    default_performance = performance_df[
        (performance_df['eigenvalue_ratio_threshold'] == DEFAULT_EIGENVALUE_RATIO_THRESHOLD) &
        (performance_df['step_alignment_threshold'] == DEFAULT_STEP_ALIGNMENT_THRESHOLD)
    ]

    if len(default_performance) > 0:
        summary['default_f1_score'] = default_performance['f1_score'].values[0]
        summary['default_accuracy'] = default_performance['accuracy'].values[0]
        summary['default_precision'] = default_performance['precision'].values[0]
        summary['default_recall'] = default_performance['recall'].values[0]

    # Save summary to CSV
    pd.DataFrame([summary]).to_csv(os.path.join(output_dir, "threshold_summary.csv"), index=False)

    return summary


def create_summary_report(metrics_df, threshold_summary, output_dir):
    """Create a summary report of the analysis.

    Args:
        metrics_df: DataFrame with calculated metrics
        threshold_summary: Dictionary with threshold analysis results
        output_dir: Directory to save the report
    """
    # Create output file
    report_path = os.path.join(output_dir, "summary_report.md")

    # Calculate summary statistics for each motion type
    summary_stats = metrics_df.groupby('motion_type').agg({
        'eigenvalue_ratio': ['mean', 'std', 'min', 'max'],
        'step_alignment': ['mean', 'std', 'min', 'max'],
        'directionality_ratio': ['mean', 'std', 'min', 'max'],
        'asymmetry': ['mean', 'std', 'min', 'max'],
        'sRg_tensor': ['mean', 'std', 'min', 'max']
    })

    # Write report
    with open(report_path, 'w') as f:
        f.write("# Trajectory Analysis Summary Report\n\n")

        f.write("## Overview\n\n")
        f.write(f"This report summarizes the analysis of synthetic trajectories for different motion types:\n")
        for motion_type in metrics_df['motion_type'].unique():
            count = len(metrics_df[metrics_df['motion_type'] == motion_type])
            f.write(f"- {motion_type.replace('_', ' ').title()}: {count} trajectories\n")
        f.write("\n")

        f.write("## Optimal Threshold Values\n\n")
        f.write(f"Based on the analysis of the synthetic trajectories, the following threshold values are recommended:\n\n")
        f.write(f"- **Eigenvalue Ratio Threshold**: {threshold_summary['optimal_eigenvalue_ratio_threshold']:.2f}\n")
        f.write(f"- **Step Alignment Threshold**: {threshold_summary['optimal_step_alignment_threshold']:.2f}\n")
        f.write(f"- **Directionality Ratio Threshold**: {DEFAULT_DIRECTIONALITY_THRESHOLD:.2f} (default)\n\n")

        f.write("These thresholds yield an optimal F1 score of ")
        f.write(f"{threshold_summary['optimal_f1_score']:.3f} for distinguishing linear from non-linear trajectories.\n\n")

        if 'default_f1_score' in threshold_summary:
            f.write("For comparison, the default thresholds ")
            f.write(f"(Eigenvalue Ratio: {DEFAULT_EIGENVALUE_RATIO_THRESHOLD}, ")
            f.write(f"Step Alignment: {DEFAULT_STEP_ALIGNMENT_THRESHOLD}) ")
            f.write(f"yield an F1 score of {threshold_summary['default_f1_score']:.3f}.\n\n")

        f.write("## Summary Statistics by Motion Type\n\n")
        f.write("### Eigenvalue Ratio\n\n")
        f.write("| Motion Type | Mean | Std Dev | Min | Max |\n")
        f.write("|------------|------|---------|-----|-----|\n")
        for motion_type in metrics_df['motion_type'].unique():
            stats = summary_stats.loc[motion_type, 'eigenvalue_ratio']
            f.write(f"| {motion_type.replace('_', ' ').title()} | ")
            f.write(f"{stats['mean']:.2f} | {stats['std']:.2f} | ")
            f.write(f"{stats['min']:.2f} | {stats['max']:.2f} |\n")
        f.write("\n")

        f.write("### Step Alignment\n\n")
        f.write("| Motion Type | Mean | Std Dev | Min | Max |\n")
        f.write("|------------|------|---------|-----|-----|\n")
        for motion_type in metrics_df['motion_type'].unique():
            stats = summary_stats.loc[motion_type, 'step_alignment']
            f.write(f"| {motion_type.replace('_', ' ').title()} | ")
            f.write(f"{stats['mean']:.2f} | {stats['std']:.2f} | ")
            f.write(f"{stats['min']:.2f} | {stats['max']:.2f} |\n")
        f.write("\n")

        f.write("### Directionality Ratio\n\n")
        f.write("| Motion Type | Mean | Std Dev | Min | Max |\n")
        f.write("|------------|------|---------|-----|-----|\n")
        for motion_type in metrics_df['motion_type'].unique():
            stats = summary_stats.loc[motion_type, 'directionality_ratio']
            f.write(f"| {motion_type.replace('_', ' ').title()} | ")
            f.write(f"{stats['mean']:.2f} | {stats['std']:.2f} | ")
            f.write(f"{stats['min']:.2f} | {stats['max']:.2f} |\n")
        f.write("\n")

        f.write("## Classification Approach\n\n")
        f.write("Based on the analysis, the following approach is recommended for classifying trajectories:\n\n")
        f.write("1. **Linear vs Non-Linear Classification**:\n")
        f.write(f"   - A trajectory is considered **linear** if:\n")
        f.write(f"     - Eigenvalue Ratio ≥ {threshold_summary['optimal_eigenvalue_ratio_threshold']:.2f} AND\n")
        f.write(f"     - Step Alignment ≥ {threshold_summary['optimal_step_alignment_threshold']:.2f}\n\n")

        f.write("2. **Unidirectional vs Bidirectional Classification**:\n")
        f.write("   - For trajectories classified as linear:\n")
        f.write(f"     - If Directionality Ratio ≥ {DEFAULT_DIRECTIONALITY_THRESHOLD:.2f}, the trajectory is **unidirectional**\n")
        f.write(f"     - Otherwise, the trajectory is **bidirectional**\n\n")

        f.write("## Visualization\n\n")
        f.write("Several visualizations have been generated to help interpret the results:\n\n")
        f.write("- Example trajectories for each motion type\n")
        f.write("- Distribution plots for key metrics\n")
        f.write("- 3D metric space visualization\n")
        f.write("- ROC curves for classification performance\n")
        f.write("- Threshold optimization heatmap\n\n")

        f.write("These visualizations can be found in the 'plots' directory.\n\n")

        f.write("## Conclusion\n\n")
        f.write("The tensor-based method effectively distinguishes different types of motion, ")
        f.write("particularly linear from non-linear trajectories. ")
        f.write("The eigenvalue ratio and step alignment metrics are the most discriminative ")
        f.write("for identifying linear motion, while the directionality ratio helps ")
        f.write("differentiate between unidirectional and bidirectional linear motion.\n\n")

        f.write("For optimal classification performance, ")
        f.write(f"use an eigenvalue ratio threshold of {threshold_summary['optimal_eigenvalue_ratio_threshold']:.2f} ")
        f.write(f"and a step alignment threshold of {threshold_summary['optimal_step_alignment_threshold']:.2f}.\n")

    print(f"Saved summary report to {report_path}")


def main():
    """Main function to run the trajectory generation and analysis."""
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Generating synthetic trajectories...")
    trajectories = generate_trajectories(N_TRAJECTORIES, N_POINTS)

    print("Converting trajectories to DataFrames...")
    dataframes = trajectories_to_dataframe(trajectories)

    print("Saving trajectories to CSV files...")
    combined_df = save_trajectories_to_csv(dataframes, OUTPUT_DIR)

    print("Calculating metrics for all trajectories...")
    metrics_df = calculate_metrics_for_all_trajectories(trajectories)

    print("Saving metrics to CSV...")
    metrics_df.to_csv(os.path.join(OUTPUT_DIR, "trajectory_metrics.csv"), index=False)

    print("Creating trajectory plots...")
    create_trajectory_plots(trajectories, OUTPUT_DIR)

    print("Creating metric distribution plots...")
    create_metric_distribution_plots(metrics_df, OUTPUT_DIR)

    print("Analyzing classification performance...")
    threshold_summary = analyze_classification_performance(metrics_df, OUTPUT_DIR)

    print("Creating summary report...")
    create_summary_report(metrics_df, threshold_summary, OUTPUT_DIR)

    print("\nAnalysis complete! Results saved to:", OUTPUT_DIR)
    print("\nRecommended threshold values:")
    print(f"- Eigenvalue Ratio: {threshold_summary['optimal_eigenvalue_ratio_threshold']:.2f}")
    print(f"- Step Alignment: {threshold_summary['optimal_step_alignment_threshold']:.2f}")
    print(f"- Directionality Ratio: {DEFAULT_DIRECTIONALITY_THRESHOLD:.2f} (default)")


if __name__ == "__main__":
    main()
