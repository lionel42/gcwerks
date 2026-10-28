import shutil

import numpy as np
import pandas as pd
import pytest

from gcwerks.config import GCWerksConfig
from gcwerks.io.conf import NO_SITE, site_code
from gcwerks.io.standards import (
    read_standards,
    read_standards_factors,
    write_standards,
)
from gcwerks.io.text import read_table, yymmdd_to_datetime
from gcwerks.paths import GCWerksPaths
from gcwerks.standards import Standards


def test_config(config, gcdir):
    assert config.gases == ["CFC-12", "N2O"]
    assert config.reference_tank("N2O") == "H-002"
    assert config.resolve_gas("CFC12") == "CFC-12"
    assert config.resolve_gas("nitrous_oxide") == "N2O"
    assert config.resolve_gas("n2o") == "N2O"
    assert config.conf_path("example-path") == gcdir / "other" / "dir"
    assert config.conf_path("not-set") is None


def test_config_subclass_paths(gcdir):
    class MyPaths(GCWerksPaths):
        @property
        def extra(self):
            return self.path("extra")

    class MyConfig(GCWerksConfig):
        paths_class = MyPaths

    assert MyConfig.from_dir(gcdir).paths.extra == gcdir / "extra"


@pytest.mark.parametrize("name", ["peak.list", "site.codes", "gcwerks.conf"])
def test_config_missing_file_raises(tmp_path, gcdir, name):
    shutil.copytree(gcdir, tmp_path / "gcdir")
    (tmp_path / "gcdir" / "config" / name).unlink()
    with pytest.raises(FileNotFoundError):
        GCWerksConfig.from_dir(tmp_path / "gcdir")


def test_site_code(config):
    assert site_code("sio-medusa", config.site_codes) == "SIO"
    assert site_code("zep-medusa", config.site_codes) == NO_SITE


def test_read_table(tmp_path):
    path = tmp_path / "table"
    path.write_text("# comment\na b extra tokens\nc\n")
    table = read_table(path, ["x", "y"], required=1)
    assert table.to_dict("list") == {"x": ["a", "c"], "y": ["b", np.nan]}
    with pytest.raises(FileNotFoundError):
        read_table(tmp_path / "none", ["x"])


def test_yymmdd_century():
    dates = yymmdd_to_datetime(pd.Series(["990101", "240229"]))
    assert list(dates.dt.year) == [1999, 2024]
    assert yymmdd_to_datetime("240110") == pd.Timestamp("2024-01-10")


def test_standards_zero_is_missing(config):
    values = read_standards(config.paths.standards)
    assert values.loc["H-001", "CFC-12"] == 540.0
    assert np.isnan(values.loc["H-001", "N2O"])


def test_standards_roundtrip(tmp_path):
    values = pd.DataFrame({"A": [1.5, np.nan], "B": [np.nan, 2.0]}, index=["T-2", "T-1"])
    path = tmp_path / "standards"
    write_standards(values, path, ["A", "B"], exclude=["T-2"])
    back = read_standards(path)
    assert list(back.index) == ["T-1"]
    assert back.loc["T-1", "B"] == 2.0


def test_factors(config):
    factors = read_standards_factors(config.paths.standards_factors)
    assert factors["N2O"] == 330.0


def test_drift_interpolation(config):
    standards = Standards.from_files(drifts=[config.paths.standards_drift])
    times = pd.to_datetime(["2023-06-01", "2024-01-01", "2024-07-01", "2025-06-01"])
    values = standards.get_values(["J-102"] * 4, "CFC-12", times)
    assert values[0] == values[1] == pytest.approx(1.10)
    assert values[2] == pytest.approx(1.10 - 0.01 * 182 / 365)
    assert values[3] == pytest.approx(1.09)


def test_drift_wins_over_value(config):
    standards = Standards.from_files(drifts=[config.paths.standards_drift])
    standards.set_value("J-102", "CFC-12", 5.0)
    standards.set_value("J-101", "CFC-12", 1.2)
    values = standards.get_values(
        ["J-102", "J-101", "NOPE"], "CFC-12", [pd.Timestamp("2024-01-01")] * 3
    )
    np.testing.assert_allclose(values, [1.10, 1.2, np.nan])


def test_drift_curve(config):
    standards = Standards.from_files(drifts=[config.paths.standards_drift])
    curve = standards.drift_curve("J-102", "CFC-12")
    assert curve.index[0] == pd.Timestamp("2024-01-01")
    assert curve.iloc[-1] == pytest.approx(1.09)
    assert standards.drift_curve("J-101", "CFC-12").empty


def test_relative_root_is_absolute(gcdir, monkeypatch, tmp_path):
    monkeypatch.chdir(gcdir.parent)
    paths = GCWerksPaths(f"../{gcdir.parent.name}/{gcdir.name}")
    assert paths.root == gcdir
    monkeypatch.chdir(tmp_path)  # later chdir doesn't change the paths
    assert paths.peak_list.is_file()


def test_home_is_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert GCWerksPaths("~/gc").root == tmp_path / "gc"


def test_resolve(gcdir, tmp_path):
    paths = GCWerksPaths(gcdir)
    assert paths.resolve("../x/./y") == gcdir.parent / "x" / "y"
    assert paths.resolve(tmp_path) == tmp_path


def _drift(fit, p0, p1):
    return pd.DataFrame(
        {
            "tank": ["G-189"],
            "gas": ["CH3I"],
            "fit": [fit],
            "r0": [1.0],
            "p0": [p0],
            "r1": [2.0],
            "p1": [p1],
            "t0": [pd.Timestamp("2011-01-01")],
            "t1": [pd.Timestamp("2012-01-01")],
        }
    )


def test_drift_fit0_is_logarithmic_in_pressure():
    standards = Standards(drift=_drift(0, 900.0, 100.0))
    start, end = pd.Timestamp("2011-01-01"), pd.Timestamp("2012-01-01")
    middle = start + (end - start) / 2  # pressure 500
    values = standards.get_values(
        ["G-189"] * 5,
        "CH3I",
        [pd.Timestamp("2010-01-01"), start, middle, end, pd.Timestamp("2013-01-01")],
    )
    expected = 1.0 + np.log(500 / 900) / np.log(100 / 900)
    np.testing.assert_allclose(values, [1.0, 1.0, expected, 2.0, 2.0])
    assert expected < 1.5  # grows faster as the tank empties


def test_drift_fit0_without_pressures_is_linear():
    standards = Standards(drift=_drift(0, np.nan, 0.0))
    start, end = pd.Timestamp("2011-01-01"), pd.Timestamp("2012-01-01")
    values = standards.get_values(["G-189"], "CH3I", [start + (end - start) / 2])
    np.testing.assert_allclose(values, [1.5])
