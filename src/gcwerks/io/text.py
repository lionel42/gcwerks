"""Helpers shared by the readers of GCwerks whitespace-separated text files."""

from pathlib import Path

import pandas as pd


def read_table(
    path: Path,
    names: list[str],
    required: int | None = None,
) -> pd.DataFrame:
    """Read a whitespace-separated file without header into string columns.

    Lines starting with ``#`` are ignored, extra tokens on a line are dropped
    and missing trailing tokens become NaN.

    :param path: File to read.
    :param names: Names of the leading columns to keep.
    :param required: Number of leading columns that must be present for a
        row to be kept (default: all of ``names``).
    :return: The table, all columns as strings.
    :raises FileNotFoundError: If the file does not exist.
    """
    table = pd.read_csv(
        path,
        sep=r"\s+",
        header=None,
        comment="#",
        names=names,
        usecols=range(len(names)),
        dtype=str,
    )
    required = len(names) if required is None else required
    return table.dropna(subset=names[:required]).reset_index(drop=True)


def is_number(value: object) -> bool:
    """Whether ``value`` is a number or text that :func:`float` can parse.

    Missing values (NaN) count as numbers.
    """
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def yymmdd_to_datetime(dates: pd.Series | str) -> pd.Series | pd.Timestamp:
    """Convert GCwerks ``yymmdd`` dates to timestamps.

    Years starting with ``9`` are in the 1900s, all others in the 2000s.

    :param dates: One date or a series of dates.
    :return: Timestamps at 00:00.
    """
    if isinstance(dates, str):
        return yymmdd_to_datetime(pd.Series([dates])).iloc[0]
    dates = dates.astype(str)
    century = dates.str[0].eq("9").map({True: "19", False: "20"})
    return pd.to_datetime(century + dates, format="%Y%m%d")


def pad(text: str, width: int) -> str:
    """Left-justify ``text`` to ``width`` characters, like GCwerks ``pad()``."""
    return f"{text:<{width}}"
