"""Values of standard tanks per gas, optionally drifting with time.

Equivalent of the ``Standards`` structure of GCwerks (``gcstandards.h``).
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from gcwerks.io.standards import DRIFT_COLUMNS, read_standards, read_standards_drift


def _seconds(times) -> np.ndarray:
    """Return ``times`` as float seconds since 1970."""
    return np.asarray(times, dtype="datetime64[s]").astype(np.int64).astype(float)


def _drift_values(segments: pd.DataFrame, times: np.ndarray) -> np.ndarray:
    """Evaluate the drift ``segments`` of one tank and gas at ``times``.

    Inside a segment, fit 1 is linear from ``r0`` to ``r1``. Fit 0 is
    logarithmic in the tank pressure, which falls linearly from ``p0`` to
    ``p1``: ``r0 + (r1 - r0) * ln(p / p0) / ln(p1 / p0)``. A fit 0 segment
    without two different positive pressures is linear. Consecutive segments
    are joined linearly, and times outside the drift range get the value of
    the nearest end-point.
    """
    t = _seconds(times)
    fit = segments["fit"].to_numpy(dtype=int)
    t0, t1 = _seconds(segments["t0"]), _seconds(segments["t1"])
    r0, r1, p0, p1 = (segments[column].to_numpy(dtype=float) for column in ["r0", "r1", "p0", "p1"])

    order = np.argsort(np.concatenate([t0, t1]), kind="stable")
    result = np.interp(t, np.concatenate([t0, t1])[order], np.concatenate([r0, r1])[order])

    logarithmic = (fit == 0) & (p0 > 0) & (p1 > 0) & (p0 != p1) & (t1 > t0)
    # segment x time mask: which logarithmic segment contains each time
    inside = logarithmic[:, None] & (t >= t0[:, None]) & (t <= t1[:, None])
    covered = inside.any(axis=0)
    i = inside.argmax(axis=0)[covered]  # first such segment
    pressure = p0[i] + (p1[i] - p0[i]) * (t[covered] - t0[i]) / (t1[i] - t0[i])
    result[covered] = r0[i] + (r1[i] - r0[i]) * np.log(pressure / p0[i]) / np.log(p1[i] / p0[i])
    return result


@dataclass
class Standards:
    """Values of tanks per gas, optionally drifting with time.

    :param values: Values indexed by tank, one column per gas.
    :param drift: Drift segments, see :func:`read_standards_drift`. When a
        tank has drift for a gas, it takes precedence over ``values``.
    """

    values: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(index=pd.Index([], name="tank"), dtype=float)
    )
    drift: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=DRIFT_COLUMNS))

    @classmethod
    def from_files(
        cls,
        standards: Path | None = None,
        drifts: list[Path] = (),
        aliases: dict[str, str] | None = None,
    ) -> "Standards":
        """Read a standards table and any number of drift files."""
        values = read_standards(standards, aliases) if standards is not None else cls().values
        drift = [read_standards_drift(path, aliases) for path in drifts]
        drift = pd.concat(drift, ignore_index=True) if drift else cls().drift
        return cls(values=values, drift=drift)

    def set_value(self, tank: str, gas: str, value: float) -> None:
        """Set the value of ``tank`` for ``gas``."""
        self.values.loc[tank, gas] = value

    def get_values(self, tanks: pd.Series, gas: str, times: pd.Series) -> np.ndarray:
        """Return the value of each tank for ``gas`` at the matching time.

        :param tanks: Tank names.
        :param gas: The gas.
        :param times: Timestamps, same length as ``tanks``.
        :return: The values, NaN where the tank has no value.
        """
        tanks = pd.Series(np.asarray(tanks), dtype=object)
        times = np.asarray(times, dtype="datetime64[ns]")

        column = self.values[gas] if gas in self.values.columns else pd.Series(dtype=float)
        result = tanks.map(column).to_numpy(dtype=float, copy=True)

        drift = self.drift[self.drift["gas"] == gas]
        for tank, segments in drift.groupby("tank"):
            rows = (tanks == tank).to_numpy()
            if rows.any():
                result[rows] = _drift_values(segments, times[rows])
        return result

    def drift_curve(self, tank: str, gas: str, freq: str = "D") -> pd.Series:
        """Return the drift of ``tank`` over its drift range, or an empty series."""
        segments = self.drift[(self.drift["tank"] == tank) & (self.drift["gas"] == gas)]
        if segments.empty:
            return pd.Series(dtype=float)
        times = pd.date_range(segments["t0"].min(), segments["t1"].max(), freq=freq)
        return pd.Series(_drift_values(segments, times.to_numpy()), index=times)
