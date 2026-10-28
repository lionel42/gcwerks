"""Reader of the GCwerks ``peak.list``: one gas per line, ``name scale ...``
where ``scale`` is the reference tank of the gas. Further columns are ignored.
"""

from pathlib import Path

import pandas as pd

from gcwerks.io.text import read_table


def read_peak_list(path: Path) -> pd.DataFrame:
    """Read ``peak.list``.

    :param path: The peak list file.
    :return: Columns ``name`` and ``scale`` (the reference tank), in file order.
    """
    return read_table(path, ["name", "scale"])
