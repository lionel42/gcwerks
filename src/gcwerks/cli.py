"""Helpers to build command line tools working on a GCwerks directory.

A tool with subcommands is a list of modules (or objects) with two
functions, ``add_parser(subparsers)`` and ``run(args)``::

    from gcwerks.cli import run_commands

    def main(argv=None):
        run_commands("mytool", "What it does.", [command1, command2], argv)

Each command then finds the GCwerks directory in ``args.gcdir``.
"""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from gcwerks.paths import absolute_path

GCDIR_FLAGS = ("-C", "--gcdir", "-gcdir")
LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"


class Command(Protocol):
    """A subcommand of a tool built with :func:`build_parser`."""

    def add_parser(self, subparsers: argparse._SubParsersAction) -> None:
        """Register the subcommand, setting ``run`` as default."""

    def run(self, args: argparse.Namespace) -> None:
        """Run the subcommand."""


def existing_dir(value: str) -> Path:
    """Argparse type accepting only an existing directory, made absolute."""
    path = absolute_path(value)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"not a directory: {value}")
    return path


def add_gcdir_argument(
    parser: argparse.ArgumentParser,
    help: str = "GCwerks directory (default: current directory)",
    default: str | Path = ".",
    flags: Sequence[str] = GCDIR_FLAGS,
) -> None:
    """Add the GCwerks directory argument, stored in ``args.gcdir``.

    ``-gcdir`` is accepted as in the GCwerks C programs.

    :param parser: The parser.
    :param help: Help text, e.g. to say which kind of directory is expected.
    :param default: Directory used when the argument is not given
        (``argparse.SUPPRESS``: leave ``args.gcdir`` unset).
    :param flags: The option strings.
    """
    if default is not argparse.SUPPRESS:
        default = absolute_path(default)
    parser.add_argument(*flags, dest="gcdir", type=existing_dir, default=default, help=help)


def add_verbose_argument(parser: argparse.ArgumentParser, default: int | str = 0) -> None:
    """Add ``-v`` (info) / ``-vv`` (debug), stored in ``args.verbose``.

    :param parser: The parser.
    :param default: Verbosity when not given (``argparse.SUPPRESS``: leave
        ``args.verbose`` unset).
    """
    parser.add_argument(
        "-v", "--verbose", action="count", default=default, help="-v: info, -vv: debug"
    )


def add_gas_argument(
    parser: argparse.ArgumentParser,
    required: bool = False,
    help: str = "gas name (as in peak.list, aliases accepted)",
) -> None:
    """Add ``--gas``, stored in ``args.gas``."""
    parser.add_argument("--gas", required=required, help=help)


def setup_logging(verbose: int) -> None:
    """Configure logging for a verbosity count (0: warnings, 1: info, 2+: debug)."""
    levels = {0: logging.WARNING, 1: logging.INFO}
    logging.basicConfig(level=levels.get(verbose, logging.DEBUG), format=LOG_FORMAT)


def build_parser(
    prog: str,
    description: str,
    commands: Sequence[Command],
    gcdir_help: str = "GCwerks directory (default: current directory)",
) -> argparse.ArgumentParser:
    """Build a parser with the GCwerks directory, verbosity and subcommands.

    The directory and verbosity options are accepted before or after the
    subcommand (``tool -C dir cmd`` or ``tool cmd -C dir``). When given in
    both places, the one after the subcommand wins.

    :param prog: Program name.
    :param description: Program description.
    :param commands: The subcommands.
    :param gcdir_help: Help of the directory argument.
    :return: The parser. Parsed arguments have ``gcdir``, ``verbose``,
        ``command`` and ``run``.
    """
    parser = argparse.ArgumentParser(prog=prog, description=description)
    add_gcdir_argument(parser, help=gcdir_help)
    add_verbose_argument(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in commands:
        command.add_parser(subparsers)
    add_common_arguments_to_subcommands(subparsers, gcdir_help)
    return parser


def add_common_arguments_to_subcommands(
    subparsers: argparse._SubParsersAction,
    gcdir_help: str = "GCwerks directory (default: current directory)",
) -> None:
    """Also accept the directory and verbosity options after each subcommand.

    Their defaults are suppressed in the subcommands, so they don't
    overwrite the values given before the subcommand.
    """
    unique = {id(sub): sub for sub in subparsers.choices.values()}
    for sub in unique.values():
        add_gcdir_argument(sub, help=gcdir_help, default=argparse.SUPPRESS)
        add_verbose_argument(sub, default=argparse.SUPPRESS)


def run_commands(
    prog: str,
    description: str,
    commands: Sequence[Command],
    argv: Sequence[str] | None = None,
    gcdir_help: str = "GCwerks directory (default: current directory)",
) -> None:
    """Parse ``argv``, set up logging and run the selected subcommand.

    See :func:`build_parser` for the arguments.
    """
    parser = build_parser(prog, description, commands, gcdir_help)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    args.run(args)
