"""
CLI and GUI entry points for autocorrelation analysis.

Handles command-line argument parsing, tkinter GUI dialogs for interactive
parameter input, and the main orchestration of analysis modes.
"""
import os
import sys
import glob
import time
import traceback

from config import (
    INPUT_TIME_INTERVAL, INPUT_NUM_INTERVALS,
    INPUT_FILE, INPUT_CONDITION_DIR, INPUT_EXPERIMENT_DIR,
    FILE_PATTERN, OUTPUT_DIR,
    SAVE_INDIVIDUAL_TRACKS, PLOT_INDIVIDUAL_TRACKS, MAX_TRACKS_TO_PLOT,
)
from core import process_sheet, aggregate_condition_results
from io_utils import (
    read_file, expand_file_patterns, save_averages,
    save_individual_track_results, save_stats,
    save_condition_individual_tracks, create_condition_summary,
    create_cross_condition_summary,
)
from plotting import (
    create_autocorrel_plot, plot_individual_tracks,
    create_condition_plot, create_condition_individual_tracks_plot,
    create_cross_condition_plot,
)


def get_user_inputs():
    """Get time interval and number of intervals from the user via GUI."""
    from tkinter import simpledialog, Tk

    root = Tk()
    root.withdraw()

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


def process_file(input_file, time_interval, num_intervals, output_dir, output_prefix=""):
    """
    Process a single file containing trajectory data.

    Args:
        input_file: Path to the file.
        time_interval: Time interval between frames in minutes.
        num_intervals: Number of time intervals to analyze.
        output_dir: Directory to save output files.
        output_prefix: Prefix for output filenames.

    Returns:
        Tuple of (success, results_dict, error_message).
    """
    print(f"\nProcessing file: {os.path.basename(input_file)}")

    if not os.path.exists(input_file):
        return False, None, f"Input file '{input_file}' not found."

    os.makedirs(output_dir, exist_ok=True)

    try:
        data_source, file_type = read_file(input_file)
        print(f"Detected file type: {file_type.upper()}")

        if file_type == 'excel':
            sheet_names = data_source.sheet_names
        else:
            sheet_names = list(data_source.keys())

        print(f"Found {len(sheet_names)} sheet(s)/condition(s): {', '.join(sheet_names)}")

        all_results = {}
        all_scalar_products = {}
        all_individual_tracks = {}
        output_files = {}

        total_start_time = time.time()

        for sheet_name in sheet_names:
            print(f"\nProcessing sheet/condition: {sheet_name}")
            sheet_start_time = time.time()

            try:
                if file_type == 'excel':
                    sheet_df = data_source.parse(sheet_name)
                else:
                    sheet_df = data_source[sheet_name]

                print(f"  Found {len(sheet_df)} rows of data")

                scalar_products, averages, individual_tracks = process_sheet(
                    sheet_df, time_interval, num_intervals
                )

                if scalar_products is None or averages is None:
                    print(f"  Error processing sheet {sheet_name}, skipping.")
                    continue

                all_results[sheet_name] = averages
                all_scalar_products[sheet_name] = scalar_products
                all_individual_tracks[sheet_name] = individual_tracks

                output_file = save_averages(
                    averages, output_dir, sheet_name, output_prefix, file_type
                )
                output_files[sheet_name] = output_file

                if SAVE_INDIVIDUAL_TRACKS and individual_tracks is not None:
                    save_individual_track_results(
                        individual_tracks, output_dir, sheet_name, output_prefix, file_type
                    )

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

        if not all_results:
            return False, None, "No valid results were generated. Check your input file format."

        print("\nCreating plots and summary statistics...")
        create_autocorrel_plot(all_results, output_dir, output_prefix)
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


def process_condition_folder(input_dir, file_pattern, time_interval, num_intervals, output_dir=None):
    """
    Process all matching files in a condition folder.

    Args:
        input_dir: Directory containing files for a condition.
        file_pattern: Glob pattern to match files.
        time_interval: Time interval between frames in minutes.
        num_intervals: Number of time intervals to analyze.
        output_dir: Directory to save output files.

    Returns:
        Tuple of (success_count, fail_count, results_list, condition_summary).
    """
    condition_name = os.path.basename(input_dir)
    print(f"\nProcessing condition folder: {condition_name}")

    if not os.path.isdir(input_dir):
        print(f"Error: Directory '{input_dir}' not found.")
        return 0, 0, [], None

    patterns = expand_file_patterns(file_pattern)
    files = []
    for pattern in patterns:
        file_pattern_path = os.path.join(input_dir, pattern)
        files.extend(glob.glob(file_pattern_path))

    files = sorted(list(set(files)))

    if not files:
        print(f"No files matching '{file_pattern}' found in directory.")
        return 0, 0, [], None

    print(f"Found {len(files)} file(s) matching pattern '{file_pattern}':")
    for file in files:
        print(f"  - {os.path.basename(file)}")

    if output_dir is None:
        output_dir = os.path.join(input_dir, "autocorrelation_output")

    os.makedirs(output_dir, exist_ok=True)

    success_count = 0
    fail_count = 0
    results_list = []

    for i, file_path in enumerate(files):
        filename = os.path.basename(file_path)
        file_base = os.path.splitext(filename)[0]

        print(f"\n[{i+1}/{len(files)}] Processing: {filename}")
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

    if results_list:
        summary_df, file_type, aggregated_tracks = aggregate_condition_results(
            results_list, condition_name
        )

        if summary_df is not None:
            create_condition_summary(summary_df, output_dir, condition_name, file_type)
            create_condition_plot(summary_df, output_dir, condition_name)

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


def process_experiment_directory(input_dir, file_pattern, time_interval, num_intervals):
    """
    Process an experiment directory containing multiple condition folders.

    Args:
        input_dir: Directory containing condition folders.
        file_pattern: Glob pattern to match files.
        time_interval: Time interval between frames in minutes.
        num_intervals: Number of time intervals to analyze.

    Returns:
        Tuple of (success_count, fail_count, condition_summaries).
    """
    print(f"\nProcessing experiment directory: {input_dir}")

    if not os.path.isdir(input_dir):
        print(f"Error: Directory '{input_dir}' not found.")
        return 0, 0, {}

    condition_folders = [d for d in os.listdir(input_dir)
                         if os.path.isdir(os.path.join(input_dir, d)) and not d.startswith('.')]

    if not condition_folders:
        print("No condition folders found in the experiment directory.")
        return 0, 0, {}

    print(f"Found {len(condition_folders)} condition folder(s): {', '.join(condition_folders)}")

    main_output_dir = os.path.join(input_dir, "autocorrelation_output")
    os.makedirs(main_output_dir, exist_ok=True)

    total_success_count = 0
    total_fail_count = 0
    condition_summaries = {}

    for condition_folder in condition_folders:
        condition_path = os.path.join(input_dir, condition_folder)
        condition_output_dir = os.path.join(condition_path, "autocorrelation_output")

        success_count, fail_count, _, summary_df = process_condition_folder(
            condition_path, file_pattern, time_interval, num_intervals, condition_output_dir
        )

        total_success_count += success_count
        total_fail_count += fail_count

        if summary_df is not None:
            condition_summaries[condition_folder] = summary_df

    if len(condition_summaries) > 1:
        create_cross_condition_plot(condition_summaries, main_output_dir)
        create_cross_condition_summary(condition_summaries, main_output_dir)

    print(f"\nExperiment processing complete: {total_success_count} successful, {total_fail_count} failed")
    return total_success_count, total_fail_count, condition_summaries


def run_analysis(time_interval=None, num_intervals=None, input_file=None,
                 input_condition_dir=None, input_experiment_dir=None,
                 file_pattern="*.xlsx;*.xls;*.csv", output_dir="autocorrelation_output"):
    """
    Run autocorrelation analysis programmatically.

    Args:
        time_interval: Time interval between frames in minutes.
        num_intervals: Number of time intervals to analyze.
        input_file: Path to a single file to process.
        input_condition_dir: Path to a single condition folder.
        input_experiment_dir: Path to an experiment directory.
        file_pattern: Glob pattern to match files.
        output_dir: Directory to save output files.

    Returns:
        True if analysis was successful, False otherwise.
    """
    print("\nAutocorrelation Analysis")
    print("=======================")

    if time_interval is None or num_intervals is None:
        print("Error: time_interval and num_intervals must be provided.")
        return False

    if time_interval <= 0 or num_intervals <= 0:
        print("Error: time_interval and num_intervals must be positive values.")
        return False

    if input_file is not None:
        success, _, _ = process_file(input_file, time_interval, num_intervals, output_dir)
        return success
    elif input_condition_dir is not None:
        success_count, _, _, _ = process_condition_folder(
            input_condition_dir, file_pattern, time_interval, num_intervals, output_dir
        )
        return success_count > 0
    elif input_experiment_dir is not None:
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
    1. Using config variables (for IDEs like Spyder)
    2. Command-line arguments
    3. GUI dialogs
    """
    # First check if config variables are set
    if (INPUT_TIME_INTERVAL is not None and INPUT_NUM_INTERVALS is not None and
        (INPUT_FILE is not None or INPUT_CONDITION_DIR is not None or INPUT_EXPERIMENT_DIR is not None)):

        print("Using configuration from config.py...")

        if INPUT_FILE is not None:
            success, _, _ = process_file(
                INPUT_FILE, INPUT_TIME_INTERVAL, INPUT_NUM_INTERVALS, OUTPUT_DIR
            )
            return success
        elif INPUT_CONDITION_DIR is not None:
            success_count, _, _, _ = process_condition_folder(
                INPUT_CONDITION_DIR, FILE_PATTERN, INPUT_TIME_INTERVAL,
                INPUT_NUM_INTERVALS, OUTPUT_DIR
            )
            return success_count > 0
        else:
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

            if len(sys.argv) > 3:
                path = sys.argv[3]
                file_pattern = sys.argv[4] if len(sys.argv) > 4 else "*.xlsx;*.xls;*.csv"

                if os.path.isfile(path):
                    success, _, _ = process_file(
                        path, time_interval, num_intervals, OUTPUT_DIR
                    )
                    return success
                elif os.path.isdir(path):
                    subdirs = [d for d in os.listdir(path)
                              if os.path.isdir(os.path.join(path, d)) and not d.startswith('.')]

                    if subdirs:
                        success_count, _, _ = process_experiment_directory(
                            path, file_pattern, time_interval, num_intervals
                        )
                        return success_count > 0
                    else:
                        success_count, _, _, _ = process_condition_folder(
                            path, file_pattern, time_interval, num_intervals, OUTPUT_DIR
                        )
                        return success_count > 0
                else:
                    print(f"Error: '{path}' is neither a file nor a directory.")
                    return False
            else:
                print("Error: No input file or directory specified.")
                print("Usage: python cli.py time_interval num_intervals [input_path] [file_pattern]")
                return False

        except ValueError:
            print("Error: Invalid command line arguments.")
            print("Usage: python cli.py time_interval num_intervals [input_path] [file_pattern]")
            return False

    # Finally, fall back to GUI
    else:
        from tkinter import Tk, messagebox, filedialog

        time_interval, num_intervals = get_user_inputs()
        if time_interval is None or num_intervals is None:
            print("Analysis cancelled.")
            return False

        root = Tk()
        root.withdraw()

        mode = messagebox.askquestion("Analysis Mode",
                                     "Do you want to process an experiment directory with multiple condition folders?",
                                     icon='question')

        if mode == 'yes':
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
            submode = messagebox.askquestion("Analysis Mode",
                                          "Do you want to process a condition folder with multiple files?",
                                          icon='question')

            if submode == 'yes':
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
