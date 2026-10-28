"""Readers and writers of the GCwerks standards files.

File formats:

* ``standards``: a header ``tank gas1 gas2 ...`` followed by one line per
  tank. A value of 0 means no value.
* ``standards.factors``: lines ``gas factor``, the factor converting the
  values of a standards table to concentrations.
* ``standards.drift``: lines ``tank gas fit date0 r0 p0 date1 r1 p1``. The
  value of the tank goes from ``r0`` at ``date0`` to ``r1`` at ``date1``
  (``fit`` 1: linear, 0: logarithmic in the tank pressure, which goes from
  ``p0`` to ``p1``; see :class:`gcwerks.standards.Standards`).
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from gcwerks.io.text import is_number, pad, read_table, yymmdd_to_datetime
from gcwerks.species import resolve_alias

logger = logging.getLogger(__name__)

DRIFT_COLUMNS = ["tank", "gas", "fit", "date0", "r0", "p0", "date1", "r1", "p1"]


def read_standards(path: Path, aliases: dict[str, str] | None = None) -> pd.DataFrame:
    """Read a standards table.

    :param path: The standards file.
    :param aliases: Gas aliases, applied to the header.
    :return: Values indexed by tank, one column per gas, NaN for no value
        or a non-numeric value.
    """
    table = pd.read_csv(path, sep=r"\s+", comment="#", index_col=0)
    table.index = table.index.astype(str).rename("tank")
    table.columns = resolve_alias(pd.Series(table.columns), aliases or {})
    invalid = ~table.map(is_number)
    for tank, gas in invalid.stack().loc[lambda cell: cell].index:
        logger.warning(
            f"{path}: value {table.at[tank, gas]!r} of tank {tank} for {gas} is"
            " not a number, treated as no value"
        )
    return table.mask(invalid).astype(float).replace(0.0, np.nan)


def write_standards(
    values: pd.DataFrame,
    path: Path,
    gases: list[str],
    exclude: list[str] | None = None,
    start_tank: str = "",
) -> None:
    """Write a standards table.

    :param values: Values indexed by tank, one column per gas.
    :param path: Output file.
    :param gases: Columns to write, in this order. Missing gases are written
        as 0.
    :param exclude: Tanks left out.
    :param start_tank: If set, tanks sorting before it are left out.
    """
    table = values.reindex(columns=gases).sort_index()
    keep = ~table.index.isin(exclude or [])
    if start_tank:
        keep &= table.index >= start_tank
    table = table[keep].fillna(0.0)

    header = pad("tank", 16) + "".join(f"{gas:>20}" for gas in gases)
    lines = [
        pad(tank, 16) + "".join(f"{value:20.5f}" for value in row)
        for tank, row in zip(table.index, table.to_numpy(), strict=True)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *lines]) + "\n")
    logger.info(f"wrote {len(lines)} tanks to {path}")


def read_standards_factors(path: Path, aliases: dict[str, str] | None = None) -> pd.Series:
    """Read ``standards.factors``.

    :param path: File with lines ``gas factor``.
    :param aliases: Gas aliases.
    :return: The factors indexed by gas.
    :raises ValueError: If a factor is not a number.
    """
    factors = read_table(path, ["gas", "factor"])
    factors["gas"] = resolve_alias(factors["gas"], aliases or {})
    invalid = factors[~factors["factor"].map(is_number)]
    if not invalid.empty:
        bad = ", ".join(f"{r.gas} {r.factor!r}" for r in invalid.itertuples())
        raise ValueError(f"{path}: factors are not numbers: {bad}")
    return factors.set_index("gas")["factor"].astype(float)


def read_drift_table(path: Path, aliases: dict[str, str] | None = None) -> pd.DataFrame:
    """Read a drift file, keeping the end-point values as text.

    Use this to process the end-points before applying the drift, e.g. when
    some are placeholders such as ``-``.

    :param path: The drift file.
    :param aliases: Gas aliases.
    :return: The columns of :data:`DRIFT_COLUMNS`, all as strings.
    """
    drift = read_table(path, DRIFT_COLUMNS)
    drift["gas"] = resolve_alias(drift["gas"], aliases or {})
    return drift


def read_standards_drift(path: Path, aliases: dict[str, str] | None = None) -> pd.DataFrame:
    """Read a drift file to apply it.

    :param path: The drift file.
    :param aliases: Gas aliases.
    :return: :data:`DRIFT_COLUMNS` with ``fit`` as int, the values as floats
        and the dates also as timestamps ``t0`` and ``t1``. Non-numeric
        ``p0``/``p1`` become NaN (a fit 0 segment is then linear).
    :raises ValueError: If an end-point value ``r0`` or ``r1`` is not a
        number, e.g. a ``-`` left unfilled (see ``R1drift_update``).
    """
    drift = read_drift_table(path, aliases)
    for column in ["r0", "r1"]:
        invalid = drift[~drift[column].map(is_number)]
        if not invalid.empty:
            bad = ", ".join(
                f"{r.tank} {r.gas} {getattr(r, column)!r}" for r in invalid.itertuples()
            )
            raise ValueError(f"{path}: {column} values are not numbers: {bad}")
        drift[column] = drift[column].astype(float)
    for column in ["p0", "p1"]:
        invalid = ~drift[column].map(is_number)
        for row in drift[invalid].itertuples():
            logger.warning(
                f"{path}: {column} {getattr(row, column)!r} of {row.tank} {row.gas}"
                " is not a number, set to NaN"
            )
        drift[column] = drift[column].mask(invalid).astype(float)
    drift["fit"] = drift["fit"].astype(int)
    drift["t0"] = yymmdd_to_datetime(drift["date0"])
    drift["t1"] = yymmdd_to_datetime(drift["date1"])
    return drift
