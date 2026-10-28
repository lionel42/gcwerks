"""Reader of GCwerks strip-chart files (port of ``stripchart_read.c``).

A strip-chart file starts with the number of fields (uint32), followed by
each field:

- name: 32 bytes, NUL-terminated
- time0, seconds_per_point, store_scale: float32
- npoints: int32, then 3 reserved int32
- the values times ``store_scale``, as a compressed chromatogram
  (see :mod:`gcwerks.io.compress`)

All numbers are little-endian. Values and times are computed in float32 as
in the C code.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from gcwerks.io.compress import MAXPOINTS, chromatogram_uncompress

logger = logging.getLogger(__name__)

MAXCHARTS = 100

_FIELD_HEADER = np.dtype(
    [
        ("name", "S32"),
        ("time0", "<f4"),
        ("seconds_per_point", "<f4"),
        ("store_scale", "<f4"),
        ("npoints", "<i4"),
        ("reserved", "<i4", 3),
    ]
)


@dataclass
class StripChartField:
    """One field (signal) of a strip chart."""

    name: str
    time0: np.float32
    seconds_per_point: np.float32
    store_scale: np.float32
    values: np.ndarray
    """The values (float32)."""

    @property
    def times(self) -> np.ndarray:
        """Time of each value in seconds (float32)."""
        index = np.arange(self.values.size, dtype=np.float32)
        return self.time0 + self.seconds_per_point * index

    def to_series(self) -> pd.Series:
        """The values as a series named after the field, indexed by time."""
        return pd.Series(self.values, index=pd.Index(self.times, name="time"), name=self.name)


def read_stripchart(path: Path) -> dict[str, StripChartField]:
    """Read a strip-chart file.

    As in the C code, reading stops at the first corrupted field (whose
    number of values differs from the one in its header) with a warning,
    and the fields before it are returned.

    :param path: The strip-chart file.
    :return: The fields by name, in file order.
    :raises ValueError: If the file has more than ``MAXCHARTS`` fields.
    """
    path = Path(path)
    data = path.read_bytes()
    nfields = int(np.frombuffer(data, "<u4", 1)[0])
    if nfields > MAXCHARTS:
        raise ValueError(f"{path}: too many fields: {nfields}")

    fields = {}
    pos = 4
    for _ in range(nfields):
        header = np.frombuffer(data, _FIELD_HEADER, 1, pos)[0]
        pos += _FIELD_HEADER.itemsize
        scaled, pos = chromatogram_uncompress(data, pos, MAXPOINTS)
        if scaled.size != header["npoints"]:
            logger.warning(
                "corrupted strip-chart file: %s, nread: %d, nexpected: %d",
                path,
                scaled.size,
                header["npoints"],
            )
            break
        name = header["name"].split(b"\0")[0].decode("latin-1")
        fields[name] = StripChartField(
            name=name,
            time0=header["time0"],
            seconds_per_point=header["seconds_per_point"],
            store_scale=header["store_scale"],
            values=scaled.astype(np.float32) / header["store_scale"],
        )
    return fields
