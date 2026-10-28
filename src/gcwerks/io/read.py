"""Print a strip-chart or chromatogram file: ``gcwerks-read FILE [-f FIELD ...]``.

The format is detected from the content (see :func:`detect_format`), whatever
the file name. Chromatograms have the fields ``tic`` and each ion mass.

Without ``--field``, list the fields of the file. With it, print the time
and values of the given fields, one row per time (tab-separated).
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

from gcwerks.cli import add_verbose_argument, setup_logging
from gcwerks.io.chromatogram import read_chromatogram
from gcwerks.io.stripchart import StripChartField, read_stripchart


def build_parser() -> argparse.ArgumentParser:
    """Build the parser of the strip-chart command."""
    parser = argparse.ArgumentParser(
        prog="gcwerks-read",
        description="List the fields of a GCwerks strip-chart or chromatogram file or print their values.",
    )
    parser.add_argument("file", type=Path, help="strip-chart file, or chromatogram file (*.cm)")
    parser.add_argument(
        "-f",
        "--field",
        action="append",
        dest="fields",
        metavar="NAME",
        help="print the values of this field, e.g. trap1, or tic or 43 for a chromatogram "
        "(repeat for several fields, 'all' for all)",
    )
    parser.add_argument("--sep", default="\t", help="column separator (default: tab)")
    parser.add_argument(
        "--format",
        choices=["auto", *FORMATS],
        default="auto",
        help="file format (default: detected from the content)",
    )
    add_verbose_argument(parser)
    return parser


def list_fields(fields: dict[str, StripChartField]) -> pd.DataFrame:
    """One row per field: number of points, time range and scale."""
    return pd.DataFrame(
        [
            {
                "name": f.name,
                "npoints": f.values.size,
                "time0": f.time0,
                "seconds_per_point": f.seconds_per_point,
                "time_end": f.times[-1] if f.values.size else f.time0,
                "store_scale": f.store_scale,
            }
            for f in fields.values()
        ]
    )


def list_channels(channels: dict[str, pd.Series]) -> pd.DataFrame:
    """One row per channel of a chromatogram: number of points, time range and maximum."""
    return pd.DataFrame(
        [
            {
                "name": name,
                "npoints": series.size,
                "time_start": series.index.min(),
                "time_end": series.index.max(),
                "max": series.max(),
            }
            for name, series in channels.items()
        ]
    )


FORMATS = ("stripchart", "chromatogram")


def detect_format(path: Path) -> str:
    """Whether a file is a strip chart or a chromatogram, from its first bytes.

    A strip chart starts with its number of fields followed by the name of
    the first field: printable text padded with NUL bytes. A chromatogram
    has a timestamp and small integers there, which no name looks like.

    :return: ``"stripchart"`` or ``"chromatogram"``.
    """
    with open(path, "rb") as file:
        head = file.read(36)
    name = head[4:36].rstrip(b"\0")
    if len(head) == 4 or (name.isascii() and name.decode().isprintable() and b"\0" not in name):
        return "stripchart"
    return "chromatogram"


def read(path: Path, format: str = "auto") -> tuple[str, pd.DataFrame, dict[str, pd.Series]]:
    """Read a strip-chart or chromatogram file.

    :param path: The file.
    :param format: ``"stripchart"``, ``"chromatogram"`` or ``"auto"``
        (:func:`detect_format`).
    :return: A summary line, the listing of the fields and the fields.
    """
    if format == "auto":
        format = detect_format(path)
    if format == "chromatogram":
        chromatogram = read_chromatogram(path)
        channels = chromatogram.channels()
        summary = (
            f"chromatogram: {path}, start: {chromatogram.start}, "
            f"nscans: {chromatogram.times.size}, nions: {len(chromatogram.ions)}"
        )
        return summary, list_channels(channels), channels
    fields = read_stripchart(path)
    summary = f"stripchart: {path}, nfields: {len(fields)}"
    return summary, list_fields(fields), {name: f.to_series() for name, f in fields.items()}


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    try:
        summary, listing, fields = read(args.file, args.format)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.fields:
        names = list(fields) if "all" in args.fields else args.fields
        unknown = [name for name in names if name not in fields]
        if unknown:
            parser.error(f"unknown field(s): {', '.join(unknown)} (available: {', '.join(fields)})")
    try:
        if not args.fields:
            print(summary)
            if fields:
                print(listing.to_string(index=False))
        else:
            table = pd.concat([fields[name] for name in names], axis=1)
            table.to_csv(sys.stdout, sep=args.sep)
        sys.stdout.flush()
    except BrokenPipeError:  # output piped to e.g. head
        sys.stdout = open(os.devnull, "w")


if __name__ == "__main__":
    main()
