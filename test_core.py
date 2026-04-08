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
