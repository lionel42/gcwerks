"""Reader of GCwerks mass-spectrometer chromatogram files (``*.cm``).

No GCwerks source reads these files here, so the layout was worked out from
two files: a Medusa GC-MS (quadrupole, unit masses) and a TOF (exact
masses). It starts with a 56-byte header of little-endian
int32 (float32 at offset 20):

====== ==============================================================
offset content
====== ==============================================================
0      1 (format version?)
4      start of the run, unix seconds
8-19   unknown (0, 1, 4 for the quadrupole, 0, 1, 3 for the TOF)
20     time scale (float32, 1000: scan times are in ms)
24-39  reserved (0)
40     number of channels: the total ion chromatogram plus each ion
44     number of scans for the quadrupole, 0 for the TOF
48     unknown (0)
52     number of scans
====== ==============================================================

It is followed by compressed streams (see
:mod:`gcwerks.io.compress`):

1. the time of each scan, times the time scale;
2. the total ion chromatogram (TIC), one value per scan;
3. for each ion, two streams:

   - its header and scans: the levels are ``m``, ``m + n`` and then
     ``m + n + scan`` for the ``n`` scans where the ion was measured,
     with ``m`` the bits of the mass as float32. ``scan`` is the index of
     the scan for the quadrupole, but the scan time (as in stream 1) for
     the TOF; a file whose ion scans are all scan times is read as such;
   - the ``n`` values of the ion.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from gcwerks.io.compress import chromatogram_uncompress

_HEADER = np.dtype(
    [
        ("version", "<i4"),
        ("start", "<i4"),
        ("unknown", "<i4", 3),
        ("time_scale", "<f4"),
        ("reserved", "<i4", 4),
        ("nchannels", "<i4"),
        ("unknown2", "<i4", 2),
        ("nscans", "<i4"),
    ]
)


@dataclass
class IonChromatogram:
    """Signal of one ion, measured on a subset of the scans."""

    mass: float
    scans: np.ndarray
    """Index of the scans where the ion was measured."""
    values: np.ndarray


@dataclass
class Chromatogram:
    """A mass-spectrometer chromatogram: TIC and the signal of each ion."""

    start: pd.Timestamp
    times: np.ndarray
    """Time of each scan in seconds since the start of the run."""
    tic: np.ndarray
    """Total ion chromatogram, one value per scan."""
    ions: list[IonChromatogram] = field(default_factory=list)

    def channels(self) -> dict[str, pd.Series]:
        """The TIC (``"tic"``) and each ion (named after its mass), indexed by time.

        A mass measured in more than one window gets one channel per window
        (``"43"``, ``"43_2"``, ...).
        """
        index = pd.Index(self.times, name="time")
        channels = {"tic": pd.Series(self.tic, index=index, name="tic")}
        for ion in self.ions:
            name = base = f"{ion.mass:g}"
            count = 1
            while name in channels:
                count += 1
                name = f"{base}_{count}"
            channels[name] = pd.Series(ion.values, index=index[ion.scans], name=name)
        return channels


def read_chromatogram(path: Path) -> Chromatogram:
    """Read a mass-spectrometer chromatogram file.

    :param path: The ``*.cm`` file.
    :return: The chromatogram.
    :raises ValueError: If the file does not have the expected layout.
    """
    path = Path(path)
    data = path.read_bytes()
    if len(data) < _HEADER.itemsize:
        raise ValueError(f"{path}: too short for a chromatogram header")
    header = np.frombuffer(data, _HEADER, 1)[0]
    pos = _HEADER.itemsize

    def next_stream() -> np.ndarray:
        nonlocal pos
        if pos >= len(data):
            raise ValueError(f"{path}: unexpected end of file")
        levels, pos = chromatogram_uncompress(data, pos, maxpoints=2**31 - 1)
        return levels

    stored_times = next_stream()
    tic = next_stream()
    if stored_times.size != header["nscans"] or tic.size != header["nscans"]:
        raise ValueError(
            f"{path}: {stored_times.size} times and {tic.size} TIC values, "
            f"expected {header['nscans']} scans"
        )

    ions = []
    for _ in range(header["nchannels"] - 1):
        scans, values = next_stream(), next_stream()
        mass = float(np.int32(scans[0]).view(np.float32))
        npoints = int(scans[1]) - int(scans[0])
        scans = scans[2:].astype(np.int64) - scans[1]
        if not npoints == scans.size == values.size:
            raise ValueError(f"{path}: inconsistent ion stream for mass {mass:g}")
        ions.append(IonChromatogram(mass, scans, values))
    if pos != len(data):
        raise ValueError(f"{path}: {len(data) - pos} unread bytes after the last ion")

    # stored times are increasing: an ion scan is a time if it is found there
    positions = [np.searchsorted(stored_times, ion.scans) for ion in ions]
    if ions and all(
        (found < stored_times.size).all()
        and (stored_times[np.minimum(found, stored_times.size - 1)] == ion.scans).all()
        for ion, found in zip(ions, positions)
    ):
        for ion, found in zip(ions, positions):
            ion.scans = found
    for ion in ions:
        if ion.scans.size and (ion.scans.min() < 0 or ion.scans.max() >= stored_times.size):
            raise ValueError(f"{path}: scans of mass {ion.mass:g} out of range")
    times = stored_times / np.float64(header["time_scale"])

    return Chromatogram(
        start=pd.Timestamp(int(header["start"]), unit="s"),
        times=times,
        tic=tic,
        ions=ions,
    )
