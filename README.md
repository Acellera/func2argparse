# func2argparse

Converts annotated python functions to argparsers.

func2argparse uses type hints and default values in function signatures and combines them together with
the docstring of the function to create an argument parser out of it.

Choices for arguments are taken from the docstrings as demonstrated in the example below.
Boolean arguments must always be default `False`.

## Documentation & Installation

```sh
pip install func2argparse
```

## Examples

```py
from pathlib import Path

def foo(
    x: int,
    y: Path,
    z: int = 54,
    w: list[str] = ("hey", "ho"),
    k: str = "choice1",
    ll: list[int] = None,
    flg: bool = False,
    lb: list[bool] = True,
):
    """This is a test function

    Parameters
    ----------
    x : int
        First arg
    y : Path
        Second arg
    z : int
        Third arg
    w : list[str]
        Fourth arg.
        Multiline documentation
    k : str, choices=("choice1", "choice2")
        Fifth arg
    ll : list[int]
        This is an empty list
    flg : bool
        Set to True to do something
    lb : list[bool]
        A list of boolean values

    Examples
    --------
    >>> foo()
    """
    print(locals())

from func2argparse import func_to_argparser
parser = func_to_argparser(foo, exit_on_error=False)
parser.print_help()
```

```
usage: This [-h] --x X --y Y [--z Z] [--w W [W ...]] [--k {choice1,choice2}] [--ll LL [LL ...]] [--flg] [--lb LB [LB ...]]

options:
  -h, --help            show this help message and exit
  --x X, -x X           First arg (default: None)
  --y Y, -y Y           Second arg (default: None)
  --z Z, -z Z           Third arg (default: 54)
  --w W [W ...], -w W [W ...]
                        Fourth arg. Multiline documentation (default: ('hey', 'ho'))
  --k {choice1,choice2}, -k {choice1,choice2}
                        Fifth arg (default: choice1)
  --ll LL [LL ...], -l LL [LL ...]
                        This is an empty list (default: None)
  --flg, -f             Set to True to do something (default: False)
  --lb LB [LB ...], -lb LB [LB ...]
                        A list of boolean values (default: True)
```
