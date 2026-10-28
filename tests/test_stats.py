import numpy as np
import pytest

from gcwerks.stats import filtered_stats


def test_outlier_rejected():
    stats = filtered_stats([1.0, 1.001, 0.999, 1.0, 1.001, 1.08])
    assert stats.count == 6
    assert stats.count_used == 5
    assert stats.mean == pytest.approx(1.0002)
    assert stats.rejected([1.08, 1.0]).tolist() == [True, False]


def test_no_filter_below_three_values():
    stats = filtered_stats([1.0, 2.0])
    assert stats.count_used == 2
    assert stats.mean == 1.5


def test_nan_ignored_and_empty():
    assert filtered_stats([np.nan, 2.0]).mean == 2.0
    empty = filtered_stats([np.nan])
    assert np.isnan(empty.mean) and empty.count == 0


def test_percent_stdev():
    stats = filtered_stats([1.0, 3.0])
    assert stats.percent_stdev == pytest.approx(100 * np.sqrt(2) / 2)
