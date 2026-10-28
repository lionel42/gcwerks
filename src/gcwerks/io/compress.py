"""Uncompression of GCwerks chromatograms (port of ``chromatogram_compress.c``).

A compressed chromatogram stores integer levels as differences to the
previous level, which mostly fit in a byte since most of a chromatogram is
baseline:

1. A little-endian int32 with the first level.
2. A string of int32 differences, until a flag switches to another width
   (int32, int16 or int8), repeats the last level, or ends the stream.

The flags of each width are the values listed in :data:`_MODES`. A repeat
flag is followed by one signed byte with the number of repeats.

Instead of reading value by value like the C code, each string of one width
is located with numpy and its levels computed with a cumulative sum.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

MAXPOINTS = 100000  # over 24 hours at 1 point/second
MAXLONG = 2000000000

# Width of the differences, and the action of each flag, for each mode.
_MODES = {
    "int": (
        np.dtype("<i4"),
        {2000000100: "byte", 2000000200: "short", 2000000250: "repeat", 2000000300: "end"},
    ),
    "short": (
        np.dtype("<i2"),
        {32100: "byte", 32400: "int", 32450: "repeat", 32500: "end"},
    ),
    "byte": (
        np.dtype("i1"),
        {126: "short", 127: "int", -127: "repeat", -126: "end"},
    ),
}


def _next_segment(
    data: bytes, pos: int, dtype: np.dtype, flags: dict[int, str]
) -> tuple[np.ndarray, int | None, int]:
    """Read values of ``dtype`` from ``pos`` up to the first flag.

    The flag is searched in windows of doubling size, so that short segments
    do not scan the rest of the data. Flags are the largest magnitudes of
    their width, so only values at least that large are checked.

    :return: The values before the flag, the flag (``None`` at end of data)
        and the position after the flag.
    """
    available = (len(data) - pos) // dtype.itemsize
    start = 0
    window = 64
    while start < available:
        count = min(window, available - start)
        chunk = np.frombuffer(data, dtype, count, pos + start * dtype.itemsize)
        for hit in np.flatnonzero(np.abs(chunk.astype(np.int64)) >= min(map(abs, flags))):
            if int(chunk[hit]) in flags:
                end = start + int(hit)
                values = np.frombuffer(data, dtype, end, pos)
                return values, int(chunk[hit]), pos + (end + 1) * dtype.itemsize
        start += count
        window *= 2
    values = np.frombuffer(data, dtype, available, pos)
    return values, None, pos + available * dtype.itemsize


def _wrap_int32(values: np.ndarray) -> np.ndarray:
    """Wrap int64 values around like an overflowing C ``int``."""
    return (values + 2**31) % 2**32 - 2**31


def chromatogram_uncompress(
    data: bytes, pos: int = 0, maxpoints: int = MAXPOINTS
) -> tuple[np.ndarray, int]:
    """Uncompress the chromatogram starting at ``pos`` in ``data``.

    The stream ends at its end flag or at the end of ``data``. Levels beyond
    ``±MAXLONG`` are stored as ``MAXLONG`` (except the first one), as in the
    C code. If more than ``maxpoints`` levels would be read, the levels up
    to ``maxpoints`` are returned with a warning.

    :param data: Bytes holding the compressed chromatogram.
    :param pos: Offset of the chromatogram in ``data``.
    :param maxpoints: Maximum number of levels.
    :return: The levels (int32) and the position after the chromatogram.
    :raises ValueError: If ``data`` has no first level at ``pos``.
    """
    if len(data) - pos < 4:
        raise ValueError(f"no chromatogram at offset {pos}")
    last_level = int(np.frombuffer(data, "<i4", 1, pos)[0])
    pos += 4

    pieces = [np.array([last_level], dtype=np.int32)]
    npoints = 1
    mode = "int"
    while True:
        dtype, flags = _MODES[mode]
        diffs, flag, pos = _next_segment(data, pos, dtype, flags)

        if diffs.size:
            allowed = max(maxpoints - npoints, 0)
            if diffs.size > allowed:
                logger.warning("chromatogram_uncompress: MAX FILE SIZE EXCEEDED")
                diffs = diffs[:allowed]
                flag = None
            levels = _wrap_int32(last_level + np.cumsum(diffs, dtype=np.int64))
            if levels.size:
                last_level = int(levels[-1])
                levels = np.where(np.abs(levels) > MAXLONG, MAXLONG, levels)
                pieces.append(levels.astype(np.int32))
                npoints += levels.size

        action = None if flag is None else flags[flag]
        if action is None or action == "end":
            break
        if action == "repeat":
            if pos >= len(data):
                break
            count = int(np.frombuffer(data, "i1", 1, pos)[0])
            pos += 1
            if count > 0:
                pieces.append(np.full(count, pieces[-1][-1], dtype=np.int32))
                npoints += count
            continue
        mode = action

    return np.concatenate(pieces), pos
