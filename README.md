# GCwerks

Python package with utilites for GCwerks https://www.gcwerks.com/

* directory structure
* text files
* binary strip-chart and chromatogram files
* command line tools


```
pip install -e .            # or: pip install -e ".[test]"
```

## Contents

```
src/gcwerks/
├── paths.py        GCWerksPaths: locations of the config/ files (subclass to add more)
├── config.py       GCWerksConfig: peak list, aliases, site codes, gcwerks.conf
├── species.py      gas aliases from openghg-defs, alias resolution
├── io/
│   ├── text.py     whitespace-table reader, yymmdd dates, pad()
│   ├── peaks.py    peak.list
│   ├── conf.py     gcwerks.conf, site.codes, instrument → site code
│   ├── standards.py standards, standards.factors and *.drift files
│   ├── compress.py chromatogram_uncompress (port of chromatogram_compress.c)
│   ├── stripchart.py strip-chart files (port of stripchart_read.c)
│   ├── chromatogram.py mass-spectrometer chromatogram files (*.cm)
│   └── read.py     gcwerks-read: print a strip-chart or chromatogram file
├── standards.py    Standards: tank values per gas, with drift
├── stats.py        mean with a 2σ filter (port of libfilter's StdevFilter)
└── cli.py          argparse helpers
```

Next to the package, `data/` has example files (also used by the tests) and
`original_files/` the GCwerks C sources that `io/compress.py` and
`io/stripchart.py` port.

## Strip charts and chromatograms

```python
from gcwerks.io.stripchart import read_stripchart
from gcwerks.io.chromatogram import read_chromatogram

fields = read_stripchart("data/261027.0657.air.1.sc")   # {name: StripChartField}
fields["trapAT1"].to_series()                           # values indexed by time (s)

chromatogram = read_chromatogram("data/261004.1054.air.7.cm")
chromatogram.start, chromatogram.times, chromatogram.tic
chromatogram.channels()["43"]                           # an ion, indexed by time (s)
```

The layout of the `*.cm` files was worked out from the example files; see
the docstring of `io/chromatogram.py`.

```
gcwerks-read FILE                  # list the fields (or ions) of the file
gcwerks-read FILE -f trapAT1       # time and values of a field, tab-separated
gcwerks-read FILE.cm -f tic -f 43  # TIC and an ion; -f all for every field
```

The format is detected from the content of the file, not its name
(`--format stripchart|chromatogram` to force it).

## Configuration

```python
import pandas as pd
from gcwerks import GCWerksConfig, Standards

config = GCWerksConfig.from_dir("/agage/R1/medusa")
config.gases                        # ["CFC-12", "N2O", ...]
config.reference_tank("CFC-12")     # the scale column of peak.list
config.resolve_gas("CFC12")         # peak.list name of an alias
config.conf_path("R1-standards-path")

standards = Standards.from_files(
    config.paths.standards, [config.paths.standards_drift], config.aliases
)
standards.get_values(["J-102"], "CFC-12", [pd.Timestamp("2024-07-01")])
```

To add the files of an application, subclass `GCWerksPaths` and point
`GCWerksConfig.paths_class` at the subclass, as `r1.paths.R1Paths` and
`r1.io.config.R1Config` do.

## Command line helpers

`gcwerks.cli` builds tools that take the GCwerks directory as an argument.
Every tool then handles the directory, logging and gas options the same way.

```python
import argparse
from gcwerks import GCWerksConfig
from gcwerks.cli import add_gas_argument, run_commands

def add_parser(subparsers):
    parser = subparsers.add_parser("show", help="show the reference tank of a gas")
    add_gas_argument(parser, required=True)
    parser.set_defaults(run=run)

def run(args):
    config = GCWerksConfig.from_dir(args.gcdir)
    print(config.reference_tank(config.resolve_gas(args.gas)))

show = argparse.Namespace(add_parser=add_parser, run=run)  # usually a module

def main(argv=None):
    run_commands("mytool", "My GCwerks tool.", [show], argv)
```

```
mytool -C /agage/R1/medusa -v show --gas CFC-12
```

| Helper | Adds |
|---|---|
| `add_gcdir_argument(parser)` | `-C` / `--gcdir` / `-gcdir` → `args.gcdir`, an existing directory, `.` by default |
| `add_verbose_argument(parser)` | `-v` (info), `-vv` (debug) → `args.verbose` |
| `add_gas_argument(parser)` | `--gas` → `args.gas` |
| `setup_logging(verbose)` | logging configured for that verbosity |
| `build_parser(prog, description, commands)` | the directory and verbosity options plus the subcommands. The options are accepted before or after the subcommand; after wins when given twice |
| `run_commands(prog, description, commands, argv)` | parses the arguments, sets up logging and runs the subcommand |

## Gas aliases

Gases keep the name written in `peak.list`. The other names of a gas are
taken from the species of
[openghg-defs](https://github.com/openghg/openghg_defs/blob/main/openghg_defs/data/species_info.json)
(the key and the `alt` names), ignoring case: `CFC12`, `cfc-12` and `CFC-12`
all resolve to the `peak.list` name `CFC-12`. GCwerks' `peak.aliases` is not
read.

## Assumptions

The GCwerks C library sources were not available, so these formats were
inferred from how the R1 programs use them. Check them against real files.

| File | Format assumed |
|---|---|
| `config/peak.list` | `name scale ...`: the 2nd column is the reference tank |
| `config/gcwerks.conf` | `key value` |
| `config/site.codes` | `site code`: `site` is an instrument-name prefix |
| `config/standards` | header `tank gas1 gas2 ...`, 0 = no value |
| `config/standards.factors` | `gas factor` |
| `*.drift` | `tank gas fit date0 r0 p0 date1 r1 p1`. `fit` 1 is linear. `fit` 0 is logarithmic in the pressure, as in the header of the drift files: `r0 + (r1 - r0) * ln(p / p0) / ln(p1 / p0)`, with `p` falling linearly from `p0` to `p1` (linear if the pressures are missing or equal). Values are held constant outside `[date0, date1]`. Several segments of one tank are joined linearly. `R0` is the base value: the meaning of `use_drift_r0` (set to 0 in `R1calc2`) is unknown |
| dates | `yymmdd`: years starting with 9 are in the 1900s |
| `StdevFilter` | mean ± 2 sample σ of all values, one rejection pass, only with ≥ 3 values |

## Tests

```
pytest
```

The tests use a small GCwerks directory in `tests/data/gcdir/`.
