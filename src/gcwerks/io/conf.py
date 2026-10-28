"""Readers of ``gcwerks.conf`` and ``site.codes``.

* ``gcwerks.conf``: ``key value`` per line.
* ``site.codes``: ``site code`` per line, where ``site`` is the prefix of
  instrument names (e.g. ``sio`` for ``sio-medusa``).
"""

from pathlib import Path

import pandas as pd

from gcwerks.io.text import read_table

NO_SITE = "---"


def read_gcwerks_conf(path: Path) -> dict[str, str]:
    """Read ``gcwerks.conf`` as ``key value`` pairs.

    :param path: The configuration file.
    :return: Mapping of keys to values (the rest of the line).
    """
    conf = {}
    for line in path.read_text().splitlines():
        tokens = line.split("#", 1)[0].split(maxsplit=1)
        if len(tokens) == 2:
            conf[tokens[0]] = tokens[1].strip()
    return conf


def read_site_codes(path: Path) -> pd.DataFrame:
    """Read ``site.codes``, the mapping from instrument prefix to site code.

    :param path: The site codes file.
    :return: Columns ``site`` and ``code``.
    """
    return read_table(path, ["site", "code"])


def site_code(instrument: str, site_codes: pd.DataFrame) -> str:
    """Return the site code of an instrument such as ``sio-medusa``.

    The first entry of ``site_codes`` whose ``site`` is a prefix of the
    instrument name wins. :data:`NO_SITE` is returned when nothing matches.
    """
    matches = site_codes[[instrument.startswith(site) for site in site_codes["site"]]]
    return matches["code"].iloc[0] if len(matches) else NO_SITE
