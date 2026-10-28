"""Mean with a standard-deviation filter.

Port of the ``StdevFilter`` of the GCwerks ``libfilter``: the values
further than ``nstdev`` standard deviations from the mean of all values are
rejected, and the statistics are recomputed on the remaining ones.
"""

from dataclasses import dataclass

import numpy as np

DEFAULT_NSTDEV = 2.0
MIN_COUNT_TO_FILTER = 3


@dataclass(frozen=True)
class FilteredStats:
    """Statistics of a set of values after the filter.

    :param mean: Mean of the values kept.
    :param stdev: Standard deviation of the values kept.
    :param count: Number of finite values.
    :param count_used: Number of values kept.
    :param lower: Values below are rejected.
    :param upper: Values above are rejected.
    """

    mean: float = np.nan
    stdev: float = np.nan
    count: int = 0
    count_used: int = 0
    lower: float = -np.inf
    upper: float = np.inf

    @property
    def percent_stdev(self) -> float:
        """Standard deviation in percent of the mean."""
        return 100.0 * self.stdev / self.mean if self.mean else np.nan

    def rejected(self, values: np.ndarray) -> np.ndarray:
        """True for the values the filter rejects."""
        values = np.asarray(values, dtype=float)
        return (values < self.lower) | (values > self.upper)


def _stdev(values: np.ndarray) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def filtered_stats(values: np.ndarray, nstdev: float = DEFAULT_NSTDEV) -> FilteredStats:
    """Return the statistics of ``values`` after rejecting outliers.

    NaN values are ignored. With fewer than 3 values nothing is rejected.

    :param values: The values.
    :param nstdev: Rejection threshold, in standard deviations.
    """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return FilteredStats()

    mean, stdev = float(values.mean()), _stdev(values)
    lower, upper = -np.inf, np.inf
    if len(values) >= MIN_COUNT_TO_FILTER and stdev > 0:
        lower, upper = mean - nstdev * stdev, mean + nstdev * stdev

    kept = values[(values >= lower) & (values <= upper)]
    return FilteredStats(
        mean=float(kept.mean()),
        stdev=_stdev(kept),
        count=len(values),
        count_used=len(kept),
        lower=lower,
        upper=upper,
    )
