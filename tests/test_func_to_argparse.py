from pathlib import Path
from typing import Optional, Union


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
    from func2argparse import func_to_manifest, manifest_to_argparser
    import argparse

    manifest = func_to_manifest(_func)
    parser = manifest_to_argparser(manifest, exit_on_error=False)

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


class _FakeCalculator:
    pass


def _func_union(
    a: Optional[str] = None,
    b: Union[str, None] = None,
    c: Optional[list[str]] = None,
    d: Optional[dict] = None,
    e: Union[str, _FakeCalculator, None] = None,
    f: Union[str, _FakeCalculator] = "default",
    g: Optional[int] = None,
    regular_int: int = 5,
):
    """Test union types

    Parameters
    ----------
    a : str
        A nullable string
    b : str
        Another nullable string
    c : list[str]
        A nullable list of strings
    d : dict
        A nullable dict
    e : str
        Multi-type union with unsupported class and None
    f : str
        Multi-type union with unsupported class
    g : int
        A nullable int
    regular_int : int
        A regular int (not nullable)
    """
    pass


def _test_union_types_manifest():
    from func2argparse import func_to_manifest

    manifest = func_to_manifest(_func_union)
    params = {p["name"]: p for p in manifest["params"]}

    assert params["a"]["type"] == "str"
    assert params["a"]["nullable"] is True

    assert params["b"]["type"] == "str"
    assert params["b"]["nullable"] is True

    assert params["c"]["type"] == "str"
    assert params["c"]["nargs"] == "+"
    assert params["c"]["nullable"] is True

    assert params["d"]["type"] == "dict"
    assert params["d"]["nullable"] is True

    assert params["e"]["type"] == "str"
    assert params["e"]["nullable"] is True

    assert params["f"]["type"] == "str"
    assert params["f"]["nullable"] is False

    assert params["g"]["type"] == "int"
    assert params["g"]["nullable"] is True

    assert params["regular_int"]["type"] == "int"
    assert params["regular_int"]["nullable"] is False


def _test_union_types_argparser():
    from func2argparse import func_to_manifest, manifest_to_argparser

    manifest = func_to_manifest(_func_union)
    parser = manifest_to_argparser(manifest, exit_on_error=False)

    test_args = {
        "a": "hello",
        "b": "world",
        "c": ["x", "y"],
        "d": '{"key": "val"}',
        "e": "test",
        "f": "test2",
        "g": 42,
    }
    args = parser.parse_args(_dict2list(test_args))
    parsed = vars(args)
    assert parsed["a"] == "hello"
    assert parsed["b"] == "world"
    assert parsed["c"] == ["x", "y"]
    assert parsed["d"] == {"key": "val"}
    assert parsed["e"] == "test"
    assert parsed["f"] == "test2"
    assert parsed["g"] == 42

    # Verify defaults are None for nullable optional args
    args_minimal = parser.parse_args([])
    parsed_min = vars(args_minimal)
    assert parsed_min["a"] is None
    assert parsed_min["b"] is None
    assert parsed_min["c"] is None
    assert parsed_min["d"] is None
    assert parsed_min["e"] is None
    assert parsed_min["f"] == "default"
    assert parsed_min["g"] is None
    assert parsed_min["regular_int"] == 5


def _func_pipe_union(
    a: str | None = None,
    b: list[str] | None = None,
    c: dict | None = None,
    d: str | _FakeCalculator | None = None,
    e: str | _FakeCalculator = "default",
    f: int | None = None,
    g: Path | None = None,
    nums: list[int] | None = None,
):
    """Test pipe-style union types

    Parameters
    ----------
    a : str
        A nullable string via pipe syntax
    b : list[str]
        A nullable list of strings via pipe syntax
    c : dict
        A nullable dict via pipe syntax
    d : str
        Multi-type pipe union with unsupported class and None
    e : str
        Multi-type pipe union with unsupported class
    f : int
        A nullable int via pipe syntax
    g : Path
        A nullable Path via pipe syntax
    nums : list[int]
        A nullable list of ints via pipe syntax
    """
    pass


def _test_pipe_union_types_manifest():
    from func2argparse import func_to_manifest

    manifest = func_to_manifest(_func_pipe_union)
    params = {p["name"]: p for p in manifest["params"]}

    assert params["a"]["type"] == "str"
    assert params["a"]["nullable"] is True

    assert params["b"]["type"] == "str"
    assert params["b"]["nargs"] == "+"
    assert params["b"]["nullable"] is True

    assert params["c"]["type"] == "dict"
    assert params["c"]["nullable"] is True

    assert params["d"]["type"] == "str"
    assert params["d"]["nullable"] is True

    assert params["e"]["type"] == "str"
    assert params["e"]["nullable"] is False

    assert params["f"]["type"] == "int"
    assert params["f"]["nullable"] is True

    assert params["g"]["type"] == "Path"
    assert params["g"]["nullable"] is True

    assert params["nums"]["type"] == "int"
    assert params["nums"]["nargs"] == "+"
    assert params["nums"]["nullable"] is True


def _test_pipe_union_types_argparser():
    from func2argparse import func_to_manifest, manifest_to_argparser

    manifest = func_to_manifest(_func_pipe_union)
    parser = manifest_to_argparser(manifest, exit_on_error=False)

    test_args = {
        "a": "hello",
        "b": ["x", "y"],
        "c": '{"key": "val"}',
        "d": "test",
        "e": "test2",
        "f": 42,
        "g": "/tmp/test.txt",
        "nums": [1, 2, 3],
    }
    args = parser.parse_args(_dict2list(test_args))
    parsed = vars(args)
    assert parsed["a"] == "hello"
    assert parsed["b"] == ["x", "y"]
    assert parsed["c"] == {"key": "val"}
    assert parsed["d"] == "test"
    assert parsed["e"] == "test2"
    assert parsed["f"] == 42
    assert parsed["g"] == Path("/tmp/test.txt")
    assert parsed["nums"] == [1, 2, 3]

    # Verify defaults are None for nullable pipe-union args
    args_minimal = parser.parse_args([])
    parsed_min = vars(args_minimal)
    assert parsed_min["a"] is None
    assert parsed_min["b"] is None
    assert parsed_min["c"] is None
    assert parsed_min["d"] is None
    assert parsed_min["e"] == "default"
    assert parsed_min["f"] is None
    assert parsed_min["g"] is None
    assert parsed_min["nums"] is None


def _func_implicit_nullable(
    a: str = None,
    b: list[int] = None,
    c: dict = None,
    d: int = None,
    e: str = "hello",
    f: int = 5,
):
    """Test implicit nullable from default=None

    Parameters
    ----------
    a : str
        A string with None default
    b : list[int]
        A list with None default
    c : dict
        A dict with None default
    d : int
        An int with None default
    e : str
        A string with non-None default
    f : int
        An int with non-None default
    """
    pass


def _test_implicit_nullable():
    from func2argparse import func_to_manifest

    manifest = func_to_manifest(_func_implicit_nullable)
    params = {p["name"]: p for p in manifest["params"]}

    assert params["a"]["nullable"] is True
    assert params["b"]["nullable"] is True
    assert params["c"]["nullable"] is True
    assert params["d"]["nullable"] is True
    assert params["e"]["nullable"] is False
    assert params["f"]["nullable"] is False
