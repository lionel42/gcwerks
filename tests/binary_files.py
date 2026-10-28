"""Writers of GCwerks strip-chart and chromatogram files, to build test data."""

import struct

SWITCH = {
    "int": {"byte": 2000000100, "short": 2000000200, "repeat": 2000000250, "end": 2000000300},
    "short": {"byte": 32100, "int": 32400, "repeat": 32450, "end": 32500},
    "byte": {"short": 126, "int": 127, "repeat": -127, "end": -126},
}
FORMAT = {"int": "<i", "short": "<h", "byte": "<b"}


def compress(levels: list[int]) -> bytes:
    """Compress ``levels`` like GCwerks: smallest width, repeats for runs."""
    out = struct.pack("<i", levels[0])
    mode = "int"
    i = 1
    while i < len(levels):
        run = 0
        while i + run < len(levels) and run < 127 and levels[i + run] == levels[i - 1]:
            run += 1
        if run >= 2:
            out += struct.pack(FORMAT[mode], SWITCH[mode]["repeat"]) + struct.pack("<b", run)
            i += run
            continue
        diff = levels[i] - levels[i - 1]
        width = "byte" if abs(diff) <= 125 else "short" if abs(diff) <= 32000 else "int"
        if width != mode:
            out += struct.pack(FORMAT[mode], SWITCH[mode][width])
            mode = width
        out += struct.pack(FORMAT[mode], diff)
        i += 1
    return out + struct.pack(FORMAT[mode], SWITCH[mode]["end"])


def field_bytes(name, time0, seconds_per_point, scale, levels) -> bytes:
    """One field of a strip-chart file."""
    header = name.encode().ljust(32, b"\0")
    header += struct.pack("<fffi3i", time0, seconds_per_point, scale, len(levels), 0, 0, 0)
    return header + compress(levels)


def stripchart_bytes(*fields: bytes) -> bytes:
    """A strip-chart file with the given fields (from :func:`field_bytes`)."""
    return struct.pack("<I", len(fields)) + b"".join(fields)


def chromatogram_bytes(times_ms, tic, ions) -> bytes:
    """A chromatogram file; ``ions`` are ``(mass, scans, values)``."""
    header = struct.pack(
        "<5if4i4i", 1, 1791111264, 0, 1, 4, 1000.0, 0, 0, 0, 0, len(ions) + 1, len(tic), 0, len(tic)
    )
    out = header + compress(times_ms) + compress(tic)
    for mass, scans, values in ions:
        bits = struct.unpack("<i", struct.pack("<f", mass))[0]
        out += compress([bits, bits + len(scans)] + [bits + len(scans) + s for s in scans])
        out += compress(values)
    return out
