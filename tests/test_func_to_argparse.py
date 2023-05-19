from pathlib import Path


def _dict2list(dd):
    ll = []
    for key, val in dd.items():
        ll.append(f"--{key}")
        if type(val) not in (list, tuple):
            if isinstance(val, bool) and val:
                continue
            ll.append(str(val))
        else:
            for vv in val:
                ll.append(str(vv))
    return ll


def _compare_results(test_args, args):
    args = vars(args)
    for key in test_args:
        if key == "y":
            assert args[key] == Path(test_args[key])
        else:
            assert args[key] == test_args[key], f"{args[key]}, {test_args[key]}"


def _func(
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
    >>> _func()
    """
    print(locals())


def _test_func2argparse():
    from func2argparse import func_to_argparser
    import argparse

    parser = func_to_argparser(_func, exit_on_error=False)

    test_args = {
        "x": 5,
        "y": "./func2argparse.py",
        "z": 42,
        "w": ["stefan", "doerr"],
        "k": "choice2",
        "ll": [84, 32],
        "flg": True,
        "lb": [False, True],
    }

    args = parser.parse_args(_dict2list(test_args))
    _compare_results(test_args, args)

    test_args = {
        "x": 5,
        "y": "./func2argparse.py",
    }
    args = parser.parse_args(_dict2list(test_args))
    _compare_results(test_args, args)

    test_args = {
        "x": "ho",  # Wrong, should be integer
        "y": "./func2argparse.py",
    }
    try:
        parser.parse_args(_dict2list(test_args))
    except argparse.ArgumentError:
        pass
    else:
        raise RuntimeError("Did not raise argument error")

    test_args = {
        "x": "7.5",  # Wrong, should be integer
        "y": "./func2argparse.py",
    }
    try:
        parser.parse_args(_dict2list(test_args))
    except argparse.ArgumentError:
        pass
    else:
        raise RuntimeError("Did not raise argument error")
