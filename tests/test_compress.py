import struct

import numpy as np
import pytest
from binary_files import compress

from gcwerks.io.compress import chromatogram_uncompress


@pytest.fixture
def levels() -> list[int]:
    rng = np.random.default_rng(0)
    diffs = rng.choice([0, 0, 0, 1, -3, 100, -5000, 30000, 70000, -1000000], 5000)
    return list(np.cumsum(diffs) + 12345)


def test_uncompress_round_trip(levels):
    data = b"xx" + compress(levels) + b"rest"
    result, pos = chromatogram_uncompress(data, 2)
    assert result.dtype == np.int32
    np.testing.assert_array_equal(result, levels)
    assert data[pos:] == b"rest"


def test_uncompress_flags_and_eof():
    # byte mode, a repeat, a short, then end of data without end flag
    data = struct.pack("<iibbbbh", 10, 2000000100, 5, -127, 3, 126, 1000)
    result, _ = chromatogram_uncompress(data)
    np.testing.assert_array_equal(result, [10, 15, 15, 15, 15, 1015])


def test_uncompress_clips_to_maxlong():
    data = struct.pack("<iiii", 1999999999, 10, -10, 2000000300)
    result, _ = chromatogram_uncompress(data)
    np.testing.assert_array_equal(result, [1999999999, 2000000000, 1999999999])


def test_uncompress_maxpoints(levels):
    result, _ = chromatogram_uncompress(compress(levels), maxpoints=100)
    np.testing.assert_array_equal(result, levels[:100])


def test_uncompress_no_data():
    with pytest.raises(ValueError):
        chromatogram_uncompress(b"\0\0")
