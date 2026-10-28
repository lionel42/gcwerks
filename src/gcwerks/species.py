"""Gas names, matched with the species of `openghg-defs`_.

A gas keeps the name written in ``peak.list``. Its aliases are all the names
that ``species_info.json`` gives to the same species (the key and the ``alt``
names), compared ignoring case.

.. _openghg-defs: https://github.com/openghg/openghg_defs
"""

import json
from functools import cache

import pandas as pd
from openghg_defs import species_info_file


@cache
def _species_names() -> list[set[str]]:
    """Lower-case names of each openghg species: its key and ``alt`` names."""
    species = json.loads(species_info_file.read_text())
    return [{name.lower() for name in [key, *info.get("alt", [])]} for key, info in species.items()]


def species_aliases(gases: list[str]) -> dict[str, str]:
    """Map the names of each gas to its name in ``gases``.

    :param gases: Gas names, e.g. from ``peak.list``.
    :return: Mapping of every lower-case name of each gas, including the gas
        name itself, to the gas name.
    :raises ValueError: If two gases are names of the same openghg species.
    """
    aliases = {}
    for gas in gases:
        names = {gas.lower()}
        for species in _species_names():
            if gas.lower() in species:
                names |= species
        for name in names:
            if aliases.get(name, gas) != gas:
                raise ValueError(f"gases {aliases[name]} and {gas} are both named {name!r}")
            aliases[name] = gas
    return aliases


def resolve_gas(name: str, aliases: dict[str, str]) -> str:
    """Return the gas named ``name``, or ``name`` if it is not an alias.

    :param name: Gas name as written in a file or given by the user.
    :param aliases: Mapping from :func:`species_aliases`.
    """
    return aliases.get(name.lower(), name)


def resolve_alias(names: pd.Series, aliases: dict[str, str]) -> pd.Series:
    """Replace gas aliases by the gas names, see :func:`resolve_gas`."""
    return names.map(lambda name: resolve_gas(name, aliases))
