import argparse
import types

import pytest

from gcwerks.cli import add_gcdir_argument, build_parser, run_commands


def test_gcdir_flags(gcdir):
    parser = argparse.ArgumentParser()
    add_gcdir_argument(parser)
    for flag in ["-C", "--gcdir", "-gcdir"]:
        assert parser.parse_args([flag, str(gcdir)]).gcdir == gcdir
    assert parser.parse_args([]).gcdir.samefile(".")


def test_gcdir_must_exist(tmp_path):
    parser = argparse.ArgumentParser()
    add_gcdir_argument(parser)
    with pytest.raises(SystemExit):
        parser.parse_args(["-C", str(tmp_path / "missing")])


def make_command(calls):
    def add_parser(subparsers):
        parser = subparsers.add_parser("hello")
        parser.add_argument("--name", default="world")
        parser.set_defaults(run=run)

    def run(args):
        calls.append((args.gcdir, args.name, args.verbose))

    return types.SimpleNamespace(add_parser=add_parser, run=run)


def test_run_commands(gcdir):
    calls = []
    run_commands(
        "tool", "A tool.", [make_command(calls)], ["-C", str(gcdir), "-vv", "hello"]
    )
    assert calls == [(gcdir, "world", 2)]


@pytest.mark.parametrize(
    "argv, expected_verbose",
    [
        (["hello", "-C", "{gcdir}", "-v"], 1),
        (["hello", "--name", "x", "-gcdir", "{gcdir}"], 0),
        (["-v", "hello", "-C", "{gcdir}"], 1),
    ],
)
def test_common_arguments_after_command(gcdir, argv, expected_verbose):
    parser = build_parser("tool", "A tool.", [make_command([])])
    args = parser.parse_args([a.format(gcdir=gcdir) for a in argv])
    assert args.gcdir == gcdir
    assert args.verbose == expected_verbose


def test_after_command_wins(gcdir, tmp_path):
    parser = build_parser("tool", "A tool.", [make_command([])])
    args = parser.parse_args(["-C", str(tmp_path), "hello", "-C", str(gcdir)])
    assert args.gcdir == gcdir


def test_defaults_without_options():
    args = build_parser("tool", "A tool.", [make_command([])]).parse_args(["hello"])
    assert args.gcdir.samefile(".") and args.verbose == 0


def test_subcommand_required():
    parser = build_parser("tool", "A tool.", [make_command([])])
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_gcdir_is_absolute(gcdir, monkeypatch):
    monkeypatch.chdir(gcdir)
    parser = argparse.ArgumentParser()
    add_gcdir_argument(parser)
    assert parser.parse_args(["-C", "config/.."]).gcdir == gcdir
    assert parser.parse_args([]).gcdir == gcdir
