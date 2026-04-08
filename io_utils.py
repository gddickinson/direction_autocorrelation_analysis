"""
File I/O utilities for autocorrelation analysis.

Handles reading Excel and CSV trajectory data, identifying columns,
and saving results in various formats.
"""
import os
import pandas as pd
from typing import Tuple, Dict, Optional, Union


def get_file_type(file_path: str) -> str:
    """
    Determine the file type based on extension.

    Args:
        file_path: Path to the file.

    Returns:
        'excel' or 'csv'.

    Raises:
        ValueError: If the file type is not supported.
    """
    _, ext = os.path.splitext(file_path.lower())
    if ext in ['.xlsx', '.xls']:
        return 'excel'
    elif ext == '.csv':
        return 'csv'
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def read_file(file_path: str) -> Tuple[Union[pd.ExcelFile, Dict[str, pd.DataFrame]], str]:
    """
    Read a file based on its extension.

    Args:
        file_path: Path to the file.

    Returns:
        Tuple of (data_source, file_type) where data_source is either
        a pd.ExcelFile or a dict of DataFrames.

    Raises:
        ValueError: If the file cannot be read.
    """
    file_type = get_file_type(file_path)

    if file_type == 'excel':
        excel_file = pd.ExcelFile(file_path)
        return excel_file, file_type

    elif file_type == 'csv':
        try:
            df = pd.read_csv(file_path)

            potential_sheet_cols = ['sheet', 'condition', 'group', 'experiment']
            sheet_col = None
            for col in potential_sheet_cols:
                if col in df.columns or col.lower() in [c.lower() for c in df.columns]:
                    sheet_col = next(c for c in df.columns if c.lower() == col.lower())
                    break

            if sheet_col:
                sheet_groups = df.groupby(sheet_col)
                sheets = {name: group.drop(sheet_col, axis=1) for name, group in sheet_groups}
            else:
                sheets = {'Sheet1': df}

            return sheets, file_type

        except Exception as e:
            print(f"Error reading CSV file: {str(e)}")
            try:
                df = pd.read_csv(file_path, encoding='latin1')
                sheets = {'Sheet1': df}
                return sheets, file_type
            except Exception as e2:
                raise ValueError(f"Failed to read CSV file: {str(e2)}")

    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def identify_columns(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Identify 'frame', 'x', 'y' columns in the dataframe regardless of their position.

    Args:
        df: Input dataframe.

    Returns:
        DataFrame with only 'frame', 'x', 'y' columns, or None if not found.
    """
    cols_lower = {col.lower(): col for col in df.columns}

    frame_col = None
    x_col = None
    y_col = None

    frame_options = ['frame', 'frames', 'frame_number', 'frameno', 'time', 'f', '#frame']
    for opt in frame_options:
        if opt in cols_lower:
            frame_col = cols_lower[opt]
            break

    x_options = ['x', 'x_coord', 'x_coordinate', 'xpos', 'x_position', 'x-position', 'x position']
    for opt in x_options:
        if opt in cols_lower:
            x_col = cols_lower[opt]
            break

    y_options = ['y', 'y_coord', 'y_coordinate', 'ypos', 'y_position', 'y-position', 'y position']
    for opt in y_options:
        if opt in cols_lower:
            y_col = cols_lower[opt]
            break

    if frame_col is None or x_col is None or y_col is None:
        print("  Warning: Could not identify all columns by name.")
        if len(df.columns) >= 6:
            try:
                frame_col = frame_col or df.columns[3]
                x_col = x_col or df.columns[4]
                y_col = y_col or df.columns[5]
                print("  Falling back to default column positions (4=frame, 5=x, 6=y)")
            except IndexError:
                print("  Error: DataFrame doesn't have enough columns for default positioning.")

        if frame_col is None or x_col is None or y_col is None:
            print(f"  Error: Could not identify all required columns.")
            print(f"  Available columns: {', '.join(df.columns)}")
            return None

    result_df = pd.DataFrame({
        'frame': df[frame_col],
        'x': df[x_col],
        'y': df[y_col]
    })

    print(f"  Using columns: '{frame_col}' as frame, '{x_col}' as x, '{y_col}' as y")
    return result_df


def expand_file_patterns(file_pattern: str) -> list:
    """
    Expand semicolon-separated file patterns into a list.

    Args:
        file_pattern: Semicolon-separated file patterns (e.g., "*.xlsx;*.csv").

    Returns:
        List of individual patterns.
    """
    return file_pattern.split(';')


def save_averages(averages: pd.DataFrame, output_dir: str, sheet_name: str,
                  output_prefix: str = "", file_type: str = "excel") -> str:
    """
    Save averages in the appropriate format.

    Args:
        averages: DataFrame with averages and SEMs.
        output_dir: Directory to save the files.
        sheet_name: Name of the sheet/condition.
        output_prefix: Prefix for output filenames.
        file_type: 'excel' or 'csv'.

    Returns:
        Path to the saved file.
    """
    base_name = f"{output_prefix}{sheet_name}_averages" if output_prefix else f"{sheet_name}_averages"

    if file_type == 'excel':
        averages_path = os.path.join(output_dir, f"{base_name}.xlsx")
        averages.to_excel(averages_path)
        print(f"  Saved averages to {averages_path}")
    else:
        averages_path = os.path.join(output_dir, f"{base_name}.csv")
        averages.to_csv(averages_path)
        print(f"  Saved averages to {averages_path}")

    return os.path.join(output_dir, f"{base_name}.{'xlsx' if file_type == 'excel' else 'csv'}")


def save_individual_track_results(tracks_df: pd.DataFrame, output_dir: str,
                                   sheet_name: str, output_prefix: str = "",
                                   file_type: str = "excel") -> str:
    """
    Save individual track results.

    Args:
        tracks_df: DataFrame with individual track results.
        output_dir: Directory to save the file.
        sheet_name: Name of the sheet/condition.
        output_prefix: Prefix for output filenames.
        file_type: 'excel' or 'csv'.

    Returns:
        Path to the saved file.
    """
    print("  Saving individual track results...")
    base_name = f"{output_prefix}{sheet_name}_individual_tracks" if output_prefix else f"{sheet_name}_individual_tracks"

    if file_type == 'excel':
        file_path = os.path.join(output_dir, f"{base_name}.xlsx")
        tracks_df.to_excel(file_path, index=False)
    else:
        file_path = os.path.join(output_dir, f"{base_name}.csv")
        tracks_df.to_csv(file_path, index=False)

    print(f"  Saved individual track results to {file_path}")
    return file_path


def save_stats(all_scalar_products: dict, output_dir: str,
               output_prefix: str = "", file_type: str = "excel") -> pd.DataFrame:
    """
    Save all scalar products for statistical analysis.

    Args:
        all_scalar_products: Dict mapping condition names to scalar products.
        output_dir: Directory to save the stats file.
        output_prefix: Prefix for output filenames.
        file_type: 'excel' or 'csv'.

    Returns:
        The stats DataFrame.
    """
    print("Saving statistics...")
    stats_dict = {}

    for condition, scalars in all_scalar_products.items():
        for col in scalars.columns:
            col_name = f"{condition} - {col}"
            values = scalars[col].dropna().values
            stats_dict[col_name] = pd.Series(values)

    stats_df = pd.DataFrame(stats_dict)
    stats_name = f"{output_prefix}autocorrelation_stats" if output_prefix else "autocorrelation_stats"

    if file_type == 'excel':
        stats_path = os.path.join(output_dir, f"{stats_name}.xlsx")
        stats_df.to_excel(stats_path, index=False)
    else:
        stats_path = os.path.join(output_dir, f"{stats_name}.csv")
        stats_df.to_csv(stats_path, index=False)

    print(f"Saved statistics to {stats_path}")
    return stats_df


def save_condition_individual_tracks(aggregated_tracks_df: pd.DataFrame, output_dir: str,
                                      condition_name: str, file_type: str) -> Optional[str]:
    """
    Save the aggregated individual track results for a condition.

    Args:
        aggregated_tracks_df: DataFrame with all individual track results.
        output_dir: Directory to save the file.
        condition_name: Name of the condition.
        file_type: 'excel' or 'csv'.

    Returns:
        Path to the saved file, or None.
    """
    if aggregated_tracks_df is None or len(aggregated_tracks_df) == 0:
        print(f"  No individual track data available for condition: {condition_name}")
        return None

    print(f"Saving individual track results for condition: {condition_name}")
    file_name = f"{condition_name}_all_individual_tracks"

    if file_type == 'excel':
        file_path = os.path.join(output_dir, f"{file_name}.xlsx")
        aggregated_tracks_df.to_excel(file_path, index=False)
    else:
        file_path = os.path.join(output_dir, f"{file_name}.csv")
        aggregated_tracks_df.to_csv(file_path, index=False)

    print(f"Saved condition individual track results to {file_path}")
    return file_path


def create_condition_summary(summary_df: pd.DataFrame, output_dir: str,
                              condition_name: str, file_type: str) -> str:
    """
    Create a summary file for a condition.

    Args:
        summary_df: DataFrame with summary statistics.
        output_dir: Directory to save the summary file.
        condition_name: Name of the condition.
        file_type: 'excel' or 'csv'.

    Returns:
        Path to the saved summary file.
    """
    print(f"Creating summary for condition: {condition_name}")
    summary_name = f"{condition_name}_summary"

    if file_type == 'excel':
        summary_path = os.path.join(output_dir, f"{summary_name}.xlsx")
        summary_df.to_excel(summary_path)
    else:
        summary_path = os.path.join(output_dir, f"{summary_name}.csv")
        summary_df.to_csv(summary_path)

    print(f"Saved condition summary to {summary_path}")
    return summary_path


def create_cross_condition_summary(condition_summaries: dict, main_output_dir: str,
                                    file_type: str = 'csv') -> str:
    """
    Create a summary file comparing all conditions.

    Args:
        condition_summaries: Dict mapping condition names to summary DataFrames.
        main_output_dir: Directory to save the summary file.
        file_type: 'excel' or 'csv'.

    Returns:
        Path to the saved summary file.
    """
    print("Creating cross-condition summary file...")
    all_conditions_df = pd.DataFrame()

    for condition, summary in condition_summaries.items():
        avg_row = summary.loc['AVG']
        avg_row.name = f"{condition}_AVG"
        all_conditions_df = pd.concat([all_conditions_df, avg_row], axis=1)

        sem_row = summary.loc['SEM']
        sem_row.name = f"{condition}_SEM"
        all_conditions_df = pd.concat([all_conditions_df, sem_row], axis=1)

    all_conditions_df = all_conditions_df.transpose()

    if file_type == 'excel':
        summary_path = os.path.join(main_output_dir, "all_conditions_summary.xlsx")
        all_conditions_df.to_excel(summary_path)
    else:
        summary_path = os.path.join(main_output_dir, "all_conditions_summary.csv")
        all_conditions_df.to_csv(summary_path)

    print(f"Saved cross-condition summary to {summary_path}")
    return summary_path
