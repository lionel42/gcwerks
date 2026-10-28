import pytest
from binary_files import chromatogram_bytes, field_bytes, stripchart_bytes

from gcwerks.io.read import detect_format, main


def test_read_stripchart(tmp_path, capsys):
    path = tmp_path / "chart.sc"
    path.write_bytes(
        stripchart_bytes(
            field_bytes("trap1", 0.0, 0.5, 10.0, [10, 20, 30]),
            field_bytes("mks_press1", 0.0, 1.0, 1.0, [7, 8]),
        )
    )
    main([str(path)])
    out = capsys.readouterr().out
    assert "nfields: 2" in out and "trap1" in out and "mks_press1" in out

    main([str(path), "-f", "trap1", "-f", "mks_press1", "--sep", ","])
    assert capsys.readouterr().out.splitlines() == [
        "time,trap1,mks_press1",
        "0.0,1.0,7.0",
        "0.5,2.0,",
        "1.0,3.0,8.0",
    ]


def test_read_chromatogram(tmp_path, capsys):
    path = tmp_path / "run.cm"
    path.write_bytes(chromatogram_bytes([0, 500, 1000], [5, 9, 7], [(43.0, [1, 2], [4, 2])]))
    main([str(path)])
    assert "nions: 1" in capsys.readouterr().out
    main([str(path), "-f", "tic", "-f", "43", "--sep", ","])
    assert capsys.readouterr().out.splitlines() == ["time,tic,43", "0.0,5,", "0.5,9,4.0", "1.0,7,2.0"]


def test_read_unknown_field(tmp_path, capsys):
    path = tmp_path / "chart.sc"
    path.write_bytes(stripchart_bytes(field_bytes("trap1", 0.0, 1.0, 1.0, [1])))
    with pytest.raises(SystemExit):
        main([str(path), "-f", "nope"])
    assert "available: trap1" in capsys.readouterr().err


def test_read_missing_file(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "missing.sc")])
    assert "No such file" in capsys.readouterr().err


def test_detect_format_ignores_name(tmp_path):
    chart = tmp_path / "chart.cm"
    chart.write_bytes(stripchart_bytes(field_bytes("trap1", 0.0, 1.0, 1.0, [1])))
    empty = tmp_path / "empty"
    empty.write_bytes(stripchart_bytes())
    run = tmp_path / "run"
    run.write_bytes(chromatogram_bytes([0, 500], [5, 9], [(43.0, [1], [4])]))
    assert detect_format(chart) == "stripchart"
    assert detect_format(empty) == "stripchart"
    assert detect_format(run) == "chromatogram"


def test_read_format_option(tmp_path, capsys):
    path = tmp_path / "run"
    path.write_bytes(chromatogram_bytes([0, 500], [5, 9], [(43.0, [1], [4])]))
    main([str(path), "--format", "chromatogram"])
    assert "nions: 1" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["261027.0657.air.1.sc", "261004.1054.air.7.cm", "261022.1857.air.1.cm"])
def test_detect_format_examples(data_dir, tmp_path, name):
    expected = "stripchart" if name.endswith(".sc") else "chromatogram"
    renamed = tmp_path / "renamed"
    renamed.write_bytes((data_dir / name).read_bytes())
    assert detect_format(renamed) == expected


@pytest.mark.parametrize(
    "name, header, field, nlines",
    [
        ("261027.0657.air.1.sc", "nfields: 31", "trapAT1", 2346),
        ("261004.1054.air.7.cm", "nions: 98", "19", 363),
        ("261022.1857.air.1.cm", "nions: 364", "tic", 18601),
    ],
)
def test_read_examples(data_dir, capsys, name, header, field, nlines):
    main([str(data_dir / name)])
    assert header in capsys.readouterr().out
    main([str(data_dir / name), "-f", field])
    assert len(capsys.readouterr().out.splitlines()) == nlines
