"""Default locations of the files inside a GCwerks directory.

Subclass :class:`GCWerksPaths` to add the files of a specific application
(e.g. ``r1.paths.R1Paths``).
"""

from dataclasses import dataclass
from pathlib import Path


def absolute_path(path: str | Path, base: str | Path | None = None) -> Path:
    """Return ``path`` as a normalized absolute path.

    :param path: The path. ``~`` is expanded.
    :param base: Directory of relative paths (default: current directory).
    """
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = Path(base).expanduser() / path if base is not None else path
    return path.resolve()


@dataclass(frozen=True)
class GCWerksPaths:
    """Resolve the standard file locations of one GCwerks directory.

    :param root: The GCwerks directory. ``~`` is expanded and a relative
        directory is made absolute from the current directory, so the paths
        stay valid if the current directory changes later.
    """

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", absolute_path(self.root))

    def path(self, relative: str | Path) -> Path:
        """Return ``relative`` inside the directory."""
        return self.root / relative

    def resolve(self, path: str | Path) -> Path:
        """Return an absolute ``path``, taking relative paths from the root.

        Use it for paths written in the GCwerks files (e.g. in
        ``gcwerks.conf``), which the C programs opened from the GCwerks
        directory.
        """
        return absolute_path(path, base=self.root)

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def peak_list(self) -> Path:
        return self.config_dir / "peak.list"

    @property
    def site_codes(self) -> Path:
        return self.config_dir / "site.codes"

    @property
    def gcwerks_conf(self) -> Path:
        return self.config_dir / "gcwerks.conf"

    @property
    def standards(self) -> Path:
        return self.config_dir / "standards"

    @property
    def standards_factors(self) -> Path:
        return self.config_dir / "standards.factors"

    @property
    def standards_drift(self) -> Path:
        return self.config_dir / "standards.drift"
