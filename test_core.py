"""
Unit tests for the core autocorrelation computation module.

Uses synthetic data with known persistence properties to validate
the autocorrelation calculations.
"""
import unittest
import numpy as np
import pandas as pd

from core import calculate_normed_vectors, calculate_scalar_products, calculate_averages
from io_utils import identify_columns, get_file_type, expand_file_patterns


class TestCalculateNormedVectors(unittest.TestCase):
    """Tests for the vector normalization function."""

    def test_straight_line_x(self):
        """Straight line in x should produce consistent unit vectors."""
        df = pd.DataFrame({
            'frame': [1, 2, 3, 4, 5],
            'x': [0.0, 1.0, 2.0, 3.0, 4.0],
            'y': [0.0, 0.0, 0.0, 0.0, 0.0],
        })
        result, traj_starts = calculate_normed_vectors(df)
        # Check that we found one trajectory
        self.assertEqual(len(traj_starts), 2)  # [0, len(df)]
        # Vectors should be defined for rows 1-4
        x_vecs = result['x_vector'].dropna()
        y_vecs = result['y_vector'].dropna()
        self.assertGreater(len(x_vecs), 0)

    def test_two_trajectories(self):
        """Frame reset should create two trajectory segments."""
        df = pd.DataFrame({
            'frame': [1, 2, 3, 1, 2, 3],
            'x': [0.0, 1.0, 2.0, 10.0, 11.0, 12.0],
            'y': [0.0, 0.0, 0.0, 5.0, 5.0, 5.0],
        })
        result, traj_starts = calculate_normed_vectors(df)
        # Should find 2 trajectories + end boundary = 3 entries
        self.assertEqual(len(traj_starts), 3)

    def test_empty_dataframe(self):
        """Empty input should not crash."""
        df = pd.DataFrame({'frame': [], 'x': [], 'y': []})
        result, traj_starts = calculate_normed_vectors(df)
        self.assertEqual(len(result), 0)


class TestCalculateScalarProducts(unittest.TestCase):
    """Tests for scalar product computation."""

    def test_perfect_persistence(self):
        """A straight line should have autocorrelation near 1.0."""
        df = pd.DataFrame({
            'frame': list(range(1, 31)),
            'x': np.arange(30, dtype=float),
            'y': np.zeros(30),
        })
        vectors_df, traj_starts = calculate_normed_vectors(df)
        combined, tracks = calculate_scalar_products(vectors_df, traj_starts, 1.0, 10)

        # Check that we got results
        self.assertGreater(len(combined.columns), 0)
        # For a straight line, all scalar products should be ~1.0
        for col in combined.columns:
            values = combined[col].dropna()
            if len(values) > 0:
                mean_val = values.mean()
                self.assertAlmostEqual(mean_val, 1.0, places=3,
                                       msg=f"Scalar product at interval {col} should be ~1.0")

    def test_random_walk_has_lower_persistence(self):
        """A random walk should have lower autocorrelation than a straight line."""
        np.random.seed(42)
        n = 200
        angles = np.cumsum(np.random.normal(0, 0.5, n))
        x = np.cumsum(np.cos(angles))
        y = np.cumsum(np.sin(angles))

        df = pd.DataFrame({
            'frame': list(range(1, n + 1)),
            'x': x,
            'y': y,
        })
        vectors_df, traj_starts = calculate_normed_vectors(df)
        combined, tracks = calculate_scalar_products(vectors_df, traj_starts, 1.0, 10)

        # Find columns with actual data
        valid_cols = [col for col in combined.columns if combined[col].dropna().shape[0] > 0]
        self.assertGreater(len(valid_cols), 1, "Should have multiple valid time intervals")

        first_col = valid_cols[0]
        last_col = valid_cols[-1]
        first_mean = combined[first_col].dropna().mean()
        last_mean = combined[last_col].dropna().mean()
        self.assertGreater(first_mean, last_mean,
                           "Autocorrelation should decay over time for random walk")


class TestCalculateAverages(unittest.TestCase):
    """Tests for the averaging function."""

    def test_averages_include_time_zero(self):
        """Averages should include the t=0 perfect correlation point."""
        scalar_products = pd.DataFrame({
            1.0: [0.9, 0.8, 0.85],
            2.0: [0.7, 0.6, 0.65],
        })
        result = calculate_averages(scalar_products)
        self.assertIn(0, result.columns)
        self.assertEqual(result.loc['AVG', 0], 1.0)
        self.assertEqual(result.loc['SEM', 0], 0.0)

    def test_averages_computation(self):
        """Check that mean and SEM are computed correctly."""
        scalar_products = pd.DataFrame({
            1.0: [1.0, 1.0, 1.0],
        })
        result = calculate_averages(scalar_products)
        self.assertAlmostEqual(result.loc['AVG', 1.0], 1.0)
        self.assertAlmostEqual(result.loc['SEM', 1.0], 0.0)


class TestIdentifyColumns(unittest.TestCase):
    """Tests for column identification."""

    def test_standard_column_names(self):
        """Standard column names should be found."""
        df = pd.DataFrame({
            'frame': [1, 2],
            'x': [0.0, 1.0],
            'y': [0.0, 0.0],
        })
        result = identify_columns(df)
        self.assertIsNotNone(result)
        self.assertIn('frame', result.columns)
        self.assertIn('x', result.columns)
        self.assertIn('y', result.columns)

    def test_case_insensitive(self):
        """Column name matching should be case-insensitive."""
        df = pd.DataFrame({
            'Frame': [1, 2],
            'X': [0.0, 1.0],
            'Y': [0.0, 0.0],
        })
        result = identify_columns(df)
        self.assertIsNotNone(result)

    def test_fallback_to_positions(self):
        """Should fall back to column positions 3,4,5 if names don't match."""
        df = pd.DataFrame({
            'a': [1, 2], 'b': [1, 2], 'c': [1, 2],
            'd': [1, 2], 'e': [0.0, 1.0], 'f': [0.0, 0.0],
        })
        result = identify_columns(df)
        self.assertIsNotNone(result)


class TestGetFileType(unittest.TestCase):
    """Tests for file type detection."""

    def test_xlsx(self):
        self.assertEqual(get_file_type("data.xlsx"), "excel")

    def test_xls(self):
        self.assertEqual(get_file_type("data.xls"), "excel")

    def test_csv(self):
        self.assertEqual(get_file_type("data.csv"), "csv")

    def test_unsupported(self):
        with self.assertRaises(ValueError):
            get_file_type("data.txt")


class TestExpandFilePatterns(unittest.TestCase):
    """Tests for file pattern expansion."""

    def test_multiple_patterns(self):
        result = expand_file_patterns("*.xlsx;*.csv")
        self.assertEqual(result, ["*.xlsx", "*.csv"])

    def test_single_pattern(self):
        result = expand_file_patterns("*.xlsx")
        self.assertEqual(result, ["*.xlsx"])


if __name__ == '__main__':
    unittest.main()


class TestIndexLabelsIndependence(unittest.TestCase):
    """Results must not depend on the DataFrame's index labels (regression: track starts were taken from labels but
    sliced by position, so every condition after the first in a multi-condition CSV came out NaN, and rows dropped for
    missing values shifted track boundaries)."""

    def _tracks(self):
        rng = np.random.default_rng(3)
        rows = []
        for _ in range(3):
            angle, x, y = rng.uniform(0, 2 * np.pi), 0.0, 0.0
            for f in range(12):
                rows.append((f, x, y))
                angle += rng.normal(0, 0.4)
                x, y = x + np.cos(angle), y + np.sin(angle)
        return pd.DataFrame(rows, columns=['frame', 'x', 'y'])

    def test_offset_labels_match_default_labels(self):
        from core import process_sheet
        df = self._tracks()
        _, ref, _ = process_sheet(df.copy(), 1.0, 8)
        shifted = df.copy()
        shifted.index = shifted.index + 100  # as groupby gives for the second condition of a CSV
        _, got, _ = process_sheet(shifted, 1.0, 8)
        pd.testing.assert_frame_equal(ref, got)
        self.assertFalse(got.loc['AVG'].iloc[:3].isna().any())

    def test_dropped_row_does_not_shift_boundaries(self):
        from core import process_sheet
        df = self._tracks()
        with_gap = df.copy()
        with_gap.loc[5, 'x'] = np.nan  # a missing value in the first track
        _, got, _ = process_sheet(with_gap, 1.0, 8)
        _, ref, _ = process_sheet(with_gap.dropna().reset_index(drop=True), 1.0, 8)
        pd.testing.assert_frame_equal(ref, got)


class TestAllLagsComputed(unittest.TestCase):
    """Every lag 1..num_intervals is computed when a track is long enough (the last lag used to be skipped)."""

    @staticmethod
    def _run(df, dt, n):
        import contextlib, io
        from core import process_sheet
        with contextlib.redirect_stdout(io.StringIO()):
            return process_sheet(df, dt, n)

    def test_last_lag_computed(self):
        df = pd.DataFrame({'frame': range(1, 31), 'x': np.arange(30.0), 'y': np.zeros(30)})
        sp, av, _ = self._run(df, 1.0, 10)
        self.assertAlmostEqual(av.loc['AVG', 10.0], 1.0)
        self.assertEqual(av.loc['SEM', 10.0], 0.0)
        self.assertEqual(sp[10.0].count(), 30 - 1 - 10)  # 29 unit vectors, pairs 10 apart

    def test_per_track_lags_limited_by_length(self):
        """A track of L points has L-1 vectors, so lags up to L-2 steps (and at most num_intervals)."""
        df = pd.DataFrame({'frame': [1, 2, 3, 4, 5] + list(range(1, 21)),
                           'x': [0, 1, 2, 3, 4] + list(range(20)), 'y': [0.0] * 25})
        _, _, tracks = self._run(df, 1.0, 10)
        lags = tracks.groupby('track_id')['time_interval'].max()
        self.assertEqual(lags['track_1'], 3.0)
        self.assertEqual(lags['track_2'], 10.0)

    def test_earlier_lags_unchanged(self):
        """Lags below num_intervals are identical to the results before the fix (frozen reference)."""
        import json
        from pathlib import Path
        ref = json.loads((Path(__file__).parent / 'tests' / 'fixtures' / 'pre_lastlag_reference.json').read_text())
        df = pd.DataFrame({'frame': ref['frame'], 'x': ref['x'], 'y': ref['y']})
        sp, av, tracks = self._run(df, ref['time_interval'], ref['num_intervals'])
        n = ref['num_intervals']
        np.testing.assert_allclose(av.loc['AVG'].to_numpy(float)[:n], np.array(ref['avg'][:n], float), rtol=0, atol=1e-15)
        np.testing.assert_allclose(av.loc['SEM'].to_numpy(float)[:n], np.array(ref['sem'][:n], float), rtol=0, atol=1e-15)
        self.assertEqual([int(sp[c].count()) for c in sp.columns][:n - 1], ref['n_pairs'][:n - 1])
        old = {(t, lag): c for t, lag, c in ref['tracks']}
        new = {(r.track_id, r.time_interval): r.correlation for r in tracks.itertuples()}
        for k, v in old.items():
            self.assertAlmostEqual(new[k], v, places=15)
        self.assertTrue(all(lag == n * ref['time_interval'] for (_, lag) in set(new) - set(old)))
        # the last lag is now finite: tracks of 40, 15 and 12 points contribute 29 + 4 + 1 pairs
        self.assertEqual(sp[n * ref['time_interval']].count(), 34)
        self.assertTrue(np.isfinite(av.loc['AVG', n * ref['time_interval']]))


class TestConditionAggregationSheets(unittest.TestCase):
    """aggregate_condition_results counts every sheet of a multi-sheet file as its own replicate (file:sheet)."""

    @staticmethod
    def _sheet_result(rows, dt=1.0, n=8):
        import contextlib, io
        from core import process_sheet
        with contextlib.redirect_stdout(io.StringIO()):
            _, av, tr = process_sheet(pd.DataFrame(rows), dt, n)
        return av, tr

    @staticmethod
    def _ref():
        import json
        from pathlib import Path
        return json.loads((Path(__file__).parent / 'tests' / 'fixtures' / 'pre_multisheet_reference.json').read_text())

    def _aggregate(self, results):
        import contextlib, io
        from core import aggregate_condition_results
        with contextlib.redirect_stdout(io.StringIO()):
            return aggregate_condition_results(results, 'cond')

    def test_every_sheet_is_a_replicate(self):
        ref = self._ref()
        (a1, t1), (a2, t2), (a3, t3) = [self._sheet_result(f) for f in ref['files']]
        results = [{'file_name': 'two.xlsx', 'results': {'ctrl': a1, 'drug': a2},
                    'individual_tracks': {'ctrl': t1, 'drug': t2}, 'file_type': 'excel'},
                   {'file_name': 'one.xlsx', 'results': {'Sheet1': a3}, 'individual_tracks': {'Sheet1': t3},
                    'file_type': 'excel'}]
        summary, _, tracks = self._aggregate(results)
        for col in a1.columns[1:]:
            vals = np.array([a1.loc['AVG', col], a2.loc['AVG', col], a3.loc['AVG', col]])
            self.assertAlmostEqual(summary.loc['AVG', float(col)], vals.mean(), places=14)
            self.assertAlmostEqual(summary.loc['SEM', float(col)], vals.std(ddof=1) / np.sqrt(3), places=14)
        self.assertEqual(sorted(tracks['file_id'].unique()), ['file_1:ctrl', 'file_1:drug', 'file_2'])
        self.assertEqual(tracks['track_id'].nunique(), len(t1['track_id'].unique()) + len(t2['track_id'].unique())
                         + len(t3['track_id'].unique()))

    def test_single_sheet_files_unchanged(self):
        """Single-sheet replicates give exactly the frozen pre-fix output (summary and tracks)."""
        ref = self._ref()
        results = []
        for f in ref['files']:
            av, tr = self._sheet_result(f, ref['time_interval'], ref['num_intervals'])
            results.append({'results': {'Sheet1': av}, 'individual_tracks': {'Sheet1': tr}, 'file_type': 'csv'})
        summary, _, tracks = self._aggregate(results)
        self.assertEqual([float(c) for c in summary.columns], ref['summary_columns'])
        np.testing.assert_array_equal(summary.loc['AVG'].to_numpy(float), np.array(ref['summary_avg'], float))
        np.testing.assert_array_equal(summary.loc['SEM'].to_numpy(float), np.array(ref['summary_sem'], float))
        for col, values in ref['tracks'].items():
            self.assertEqual(list(tracks[col]), values, col)
