import struct

import numpy as np
import pytest
from binary_files import field_bytes, stripchart_bytes

from gcwerks.io.stripchart import read_stripchart


def test_read_stripchart(tmp_path):
    levels = list(range(-500, 50000, 37))
    path = tmp_path / "chart.sc"
    path.write_bytes(
        stripchart_bytes(
            field_bytes("trap1", 1.5, 0.2, 10.0, levels),
            field_bytes("mks_press1", 0.0, 1.0, 1.0, [7, 7, 8]),
        )
    )
    fields = read_stripchart(path)
    assert list(fields) == ["trap1", "mks_press1"]

    trap = fields["trap1"]
    assert trap.values.dtype == np.float32
    np.testing.assert_array_equal(trap.values, np.float32(levels) / np.float32(10))
    assert trap.times[0] == np.float32(1.5)
    assert trap.times[-1] == np.float32(1.5) + np.float32(0.2) * np.float32(len(levels) - 1)

    series = fields["mks_press1"].to_series()
    assert series.name == "mks_press1"
    assert list(series) == [7, 7, 8]
    assert list(series.index) == [0, 1, 2]


def test_read_stripchart_corrupted(tmp_path, caplog):
    bad = bytearray(field_bytes("bad", 0.0, 1.0, 1.0, [1, 2]))
    bad[44:48] = struct.pack("<i", 3)  # npoints
    path = tmp_path / "chart.sc"
    path.write_bytes(
        stripchart_bytes(
            field_bytes("ok", 0.0, 1.0, 1.0, [1]),
            bytes(bad),
            field_bytes("x", 0, 1, 1, [1]),
        )
    )
    assert list(read_stripchart(path)) == ["ok"]
    assert "corrupted" in caplog.text


def test_read_stripchart_too_many_fields(tmp_path):
    path = tmp_path / "chart.sc"
    path.write_bytes(struct.pack("<I", 101))
    with pytest.raises(ValueError, match="too many fields"):
        read_stripchart(path)


def test_read_stripchart_example(data_dir):
    fields = read_stripchart(data_dir / "261027.0657.air.1.sc")
    assert len(fields) == 31
    trap = fields["trapAT1"]
    assert trap.values.size == 2345
    assert trap.seconds_per_point == np.float32(2.0)
    assert trap.store_scale == np.float32(100.0)
    assert trap.times[-1] == pytest.approx(4689.235, abs=1e-3)
