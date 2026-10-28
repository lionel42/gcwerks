"""The configuration of a GCwerks directory: gases, aliases, sites and
``gcwerks.conf``."""

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import ClassVar

import pandas as pd

from gcwerks.io.conf import read_gcwerks_conf, read_site_codes
from gcwerks.io.peaks import read_peak_list
from gcwerks.paths import GCWerksPaths
from gcwerks.species import resolve_gas, species_aliases


@dataclass
class GCWerksConfig:
    """The configuration of one GCwerks directory.

    Subclasses can set :attr:`paths_class` to use their own file locations.

    :param paths: Locations of the files.
    :param peaks: Gases and their reference tank, see
        :func:`gcwerks.io.peaks.read_peak_list`.
    :param aliases: Gas aliases, see :func:`gcwerks.species.species_aliases`.
    :param site_codes: See :func:`gcwerks.io.conf.read_site_codes`.
    :param conf: Content of ``gcwerks.conf``.
    """

    paths_class: ClassVar[type[GCWerksPaths]] = GCWerksPaths

    paths: GCWerksPaths
    peaks: pd.DataFrame
    aliases: dict[str, str] = field(default_factory=dict)
    site_codes: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["site", "code"])
    )
    conf: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dir(cls, root: str | Path) -> "GCWerksConfig":
        """Load the configuration of the GCwerks directory ``root``."""
        paths = cls.paths_class(root)
        peaks = read_peak_list(paths.peak_list)
        return cls(
            paths=paths,
            peaks=peaks,
            aliases=species_aliases(peaks["name"].tolist()),
            site_codes=read_site_codes(paths.site_codes),
            conf=read_gcwerks_conf(paths.gcwerks_conf),
        )

    @cached_property
    def gases(self) -> list[str]:
        """The gas names, in peak list order."""
        return self.peaks["name"].tolist()

    def reference_tank(self, gas: str) -> str:
        """Return the reference tank (the ``scale``) of ``gas``."""
        if gas not in self.gases:
            raise ValueError(f"gas {gas!r} not in reference peaks, known gases: {self.gases}")
        return self.peaks.set_index("name").loc[gas, "scale"]

    def resolve_gas(self, gas: str) -> str:
        """Return the ``peak.list`` name of ``gas``, which may be an alias."""
        return resolve_gas(gas, self.aliases)

    def conf_path(self, key: str) -> Path | None:
        """Return the path set for ``key`` in ``gcwerks.conf``, or None.

        Relative paths are resolved against the GCwerks directory.
        """
        value = self.conf.get(key, "")
        return self.paths.resolve(value) if value else None
