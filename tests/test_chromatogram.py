import numpy as np
import pandas as pd
import pytest
from binary_files import chromatogram_bytes

from gcwerks.io.chromatogram import read_chromatogram


def test_read_chromatogram(tmp_path):
    path = tmp_path / "run.cm"
    path.write_bytes(
        chromatogram_bytes(
            [0, 166, 333, 500], [5, 9, 7, 5], [(43.0, [1, 2], [4, 2]), (19.0, [0, 1, 2, 3], [5, 5, 5, 5])]
        )
    )
    chromatogram = read_chromatogram(path)
    assert chromatogram.start == pd.Timestamp("2026-10-04 10:54:24")
    np.testing.assert_array_equal(chromatogram.times, [0, 0.166, 0.333, 0.5])
    np.testing.assert_array_equal(chromatogram.tic, [5, 9, 7, 5])
    assert [ion.mass for ion in chromatogram.ions] == [43.0, 19.0]
    np.testing.assert_array_equal(chromatogram.ions[0].scans, [1, 2])

    channels = chromatogram.channels()
    assert list(channels) == ["tic", "43", "19"]
    assert list(channels["43"].index) == [0.166, 0.333]
    assert list(channels["43"]) == [4, 2]


def test_read_chromatogram_scans_as_times(tmp_path):
    # TOF files store the scan time instead of the scan index
    path = tmp_path / "run.cm"
    path.write_bytes(chromatogram_bytes([0, 17, 33, 50], [5, 9, 7, 5], [(28.0056, [17, 33], [4, 2])]))
    ion = read_chromatogram(path).ions[0]
    assert ion.mass == pytest.approx(28.0056)
    np.testing.assert_array_equal(ion.scans, [1, 2])


def test_read_chromatogram_duplicate_mass(tmp_path):
    path = tmp_path / "run.cm"
    path.write_bytes(chromatogram_bytes([0, 500], [5, 9], [(43.0, [0], [4]), (43.0, [1], [3])]))
    assert list(read_chromatogram(path).channels()) == ["tic", "43", "43_2"]


def test_read_chromatogram_truncated(tmp_path):
    path = tmp_path / "run.cm"
    path.write_bytes(chromatogram_bytes([0, 166], [5, 9], [(43.0, [1], [4])])[:-30])
    with pytest.raises(ValueError):
        read_chromatogram(path)


def test_read_chromatogram_quadrupole_example(data_dir):
    chromatogram = read_chromatogram(data_dir / "261004.1054.air.7.cm")
    assert chromatogram.start == pd.Timestamp("2026-10-04 10:54:24")
    assert chromatogram.times.size == chromatogram.tic.size == 14452
    assert chromatogram.times[-1] == pytest.approx(2399.898)
    assert len(chromatogram.ions) == 98
    ion = chromatogram.ions[0]
    assert ion.mass == 19.0
    assert ion.scans[0] == 6671
    assert ion.values.size == 362


def test_read_chromatogram_tof_example(data_dir):
    chromatogram = read_chromatogram(data_dir / "261022.1857.air.1.cm")
    assert chromatogram.start == pd.Timestamp("2026-10-22 18:57:00")
    assert chromatogram.times.size == chromatogram.tic.size == 18600
    assert len(chromatogram.ions) == 364
    ion = chromatogram.ions[0]
    assert ion.mass == pytest.approx(17.0022, abs=1e-4)
    assert chromatogram.times[ion.scans[0]] == pytest.approx(158.611)
    assert ion.values.size == 961
