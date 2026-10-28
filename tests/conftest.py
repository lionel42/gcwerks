from pathlib import Path

import pytest

from gcwerks.config import GCWerksConfig

GCDIR = Path(__file__).parent / "data" / "gcdir"
# example strip-chart and chromatogram files
EXAMPLES = Path(__file__).parent.parent / "data"


@pytest.fixture
def gcdir() -> Path:
    return GCDIR


@pytest.fixture
def config() -> GCWerksConfig:
    return GCWerksConfig.from_dir(GCDIR)


@pytest.fixture
def data_dir() -> Path:
    if not EXAMPLES.is_dir():
        pytest.skip(f"example files not found: {EXAMPLES}")
    return EXAMPLES
