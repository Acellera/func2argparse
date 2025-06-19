import argparse
from collections import OrderedDict
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("func2argparse")
except PackageNotFoundError:
    pass


class LoadFromFile(argparse.Action):
    def __init__(self, unmatched_args="error", *args, **kwargs):
        super().__init__(*args, **kwargs)
        if unmatched_args not in ("error", "warning"):
            raise RuntimeError("unmatched_args can only be set to error or warning")
        self.unmatched_args = unmatched_args

    def _error_unfound(self, key, namespace):
        if key not in namespace:
            if self.unmatched_args == "error":
                raise ValueError(f"Unknown argument in config file: {key}")
            elif self.unmatched_args == "warning":
                print(f"WARNING: Unknown argument in config file: {key}")

    # parser.add_argument('--file', type=open, action=LoadFromFile)
    def __call__(self, parser, namespace, values, option_string=None):
        import yaml
        import json

        if values.name.endswith("yaml") or values.name.endswith("yml"):
            with values as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
            for key in config.keys():
                self._error_unfound(key, namespace)
            namespace.__dict__.update(config)
        elif values.name.endswith("json"):
            with values as f:
                config = json.load(f)

            if "execid" in config and "params" in config:
                # Special case for PlayMolecule
                config = config["params"]
                for prm in config:
                    key = prm["name"]
                    self._error_unfound(key, namespace)
                    namespace.__dict__[key] = prm["value"]
            else:
                # General use case similar to yaml above
                for key in config.keys():
                    self._error_unfound(key, namespace)
                namespace.__dict__.update(config)
        else:
            raise ValueError("Configuration file must end with yaml or yml")


def _parse_docs(doc):
    import re
    from ast import literal_eval

    reg1 = re.compile(r"^(\S+)\s*:")
    reg2 = re.compile(r"choices=([\(\[].*[\)\]])")
    reg3 = re.compile(r"gui_options=(.*)")
    reg4 = re.compile(r"nargs=(\d+)")

    lines = doc.splitlines()
    try:
        name = lines[0].strip().split()[0]
    except Exception:
        name = None

    description = []
    for line in lines[1:]:
        if line.strip().startswith("Parameters"):
            break
        if len(line.strip()):
            description.append(line.strip())
    description = " ".join(description)

    argdocs = OrderedDict()
    currvar = None
    paramsection = False
    for i in range(len(lines)):
        line = lines[i].strip()
        if paramsection:
            if reg1.match(line):
                currvar = reg1.findall(line)[0]
                argdocs[currvar] = {"doc": "", "choices": None}
                choices = reg2.findall(line)
                if len(choices):
                    argdocs[currvar]["choices"] = literal_eval(choices[0])
                gui_options = reg3.findall(line)
                if len(gui_options):
                    argdocs[currvar]["gui_options"] = literal_eval(gui_options[0])
                nargs = reg4.findall(line)
                if len(nargs):
                    argdocs[currvar]["nargs"] = int(nargs[0])
            elif currvar is not None:
                # Everything after the initial variable line counts as help
                argdocs[currvar]["doc"] += line + " "
        if line.startswith("Parameters"):
            paramsection = True
        if paramsection and line == "":
            paramsection = False

    return argdocs, description, name


def _get_name_abbreviations(argnames):
    abbrevs = {"help": "h"}

    def get_abbr(name):
        pieces = name.split("_")
        for i in range(len(pieces)):
            yield "".join([p[0] for p in pieces[: i + 1]])
        # Last attempt
        name = name.replace("_", "")
        for i in range(1, len(name) + 1):
            yield name[:i]

    for argname in argnames:
        if argname[0] == "_":
            continue  # Don't add underscore arguments to argparser
        for abb in get_abbr(argname):
            if abb not in abbrevs.values():
                abbrevs[argname] = abb
                break
    return abbrevs


def _parse_function(func):
    from typing import get_origin, get_args
    import inspect
    import types

    # Get function signature and documentation
    sig = inspect.signature(func)
    doc = func.__doc__
    if doc is None:
        raise RuntimeError("Could not find documentation in the function...")

    argdocs, description, name = _parse_docs(doc)

    # Don't add underscore arguments to argparser or args, kwargs
    sigargs = []
    for argn in sig.parameters:
        if not (argn.startswith("_") or argn in ("args", "kwargs")):
            sigargs.append(argn)

    for argn in sigargs:
        if argn not in argdocs:
            raise RuntimeError(
                f"Could not find help for argument {argn} in the docstring of the function. Please document it."
            )

    for argn in argdocs:
        if argn not in sigargs:
            raise RuntimeError(
                f"Found docs for argument {argn} in the docstring which is not in the function signature. Please remove it."
            )

    for argn1, argn2 in zip(sigargs, argdocs):
        if argn1 != argn2:
            raise RuntimeError(
                f"Argument order mismatch between function signature and documentation (need to have same order). {argn1} != {argn2}"
            )

    arguments = []
    for argname in sigargs:
        params = sig.parameters[argname]

        argtype = params.annotation
        if isinstance(argtype, types.UnionType) and len(get_args(argtype)) == 2:
            # Handle the "x | None" cases
            if get_args(argtype)[0] is type(None):
                argtype = get_args(argtype)[1]
            elif get_args(argtype)[1] is type(None):
                argtype = get_args(argtype)[0]

        nargs = None
        # This is needed for compound types like: list[str]
        if get_origin(argtype) is not None:
            origtype = get_origin(argtype)
            argtype = get_args(argtype)[0]
            if origtype in (list, tuple):
                nargs = "+"
            elif origtype == dict:
                argtype = dict

        # Override the nargs if specified in the docstring
        if "nargs" in argdocs[argname]:
            nargs = argdocs[argname]["nargs"]

        default = None
        if params.default != inspect._empty:
            default = params.default
            # Don't allow empty list defaults., convert to None
            if type(default) in (list, tuple) and len(default) == 0:
                raise RuntimeError(
                    f"Please don't use empty tuples/lists as default arguments (e.g. {argname}=()). Use =None instead"
                )

        if type(argtype) == tuple:
            raise RuntimeError(
                f"Failed to get type annotation for argument '{argname}'"
            )

        argument = OrderedDict()
        argument["mandatory"] = params.default == inspect._empty
        argument["description"] = argdocs[argname]["doc"].strip()
        argument["type"] = argtype.__name__
        argument["name"] = argname
        argument["tag"] = f"--{argname.replace('_', '-')}"
        argument["value"] = default
        argument["nargs"] = nargs
        argument["choices"] = argdocs[argname]["choices"]
        if "gui_options" in argdocs[argname]:
            argument["gui_options"] = argdocs[argname]["gui_options"]
        arguments.append(argument)
    return name, description, arguments


def func_to_manifest(functions, file=None, pm_mode=True):
    import json
    import os

    if not isinstance(functions, list):
        functions = [functions]

    # Read existing manifest if it exists
    manifest = OrderedDict()

    if file is not None:
        manifestf = os.path.join(os.path.dirname(file), "manifest.json")
        if os.path.exists(manifestf):
            with open(manifestf, "r") as f:
                manifest = json.load(f)
        manifestf = os.path.join(os.path.dirname(file), "manifest.yaml")
        if os.path.exists(manifestf):
            import yaml

            with open(manifestf, "r") as f:
                manifest = yaml.load(f, Loader=yaml.FullLoader)

    for func in functions:
        name, description, arguments = _parse_function(func)
        if "functions" in manifest:
            # Find the where in the list the function is stored
            name = func.__name__
            try:
                idx = [
                    ff["function"].endswith(f".{name}") for ff in manifest["functions"]
                ].index(True)
            except ValueError:
                raise RuntimeError(
                    f"Function {name} not found in manifest.json 'functions' section. Please add it."
                )
            manifest["functions"][idx]["description"] = description
            manifest["functions"][idx]["params"] = arguments
            manifest["functions"][idx]["name"] = name
        else:  # TODO: DEPRECATE this
            if len(functions) > 1:
                raise RuntimeError(
                    "Multiple functions are not supported in the old manifest format. Please use the new manifest format."
                )

            if "name" not in manifest:
                manifest["name"] = name
            if "version" not in manifest:
                manifest["version"] = "1"
            manifest["description"] = description
            manifest["params"] = arguments

    return manifest


def _add_params_to_parser(parser, params, allow_conf_yaml, unmatched_args):
    from pathlib import Path

    if allow_conf_yaml:
        parser.add_argument(
            "--conf",
            help="Configuration YAML file to set all parameters",
            type=open,
            action=lambda *x, **y: LoadFromFile(*x, **y, unmatched_args=unmatched_args),
        )

    # Calculate abbreviations
    abbrevs = _get_name_abbreviations([x["name"] for x in params])

    type_map = {
        "Path": Path,
        "bool": bool,
        "int": int,
        "float": float,
        "str": str,
        "dict": dict,
    }
    for param in params:
        argname = param["name"]
        if param["type"] == "bool":
            if param["nargs"] is None:
                if param["value"] is True:
                    parser.add_argument(
                        f"--{argname.replace('_', '-')}",
                        help=param["description"],
                        default=True,
                        action=argparse.BooleanOptionalAction,
                    )
                else:
                    parser.add_argument(
                        f"--{argname.replace('_', '-')}",
                        f"-{abbrevs[argname]}",
                        help=param["description"],
                        action="store_true",
                    )
            else:
                parser.add_argument(
                    f"--{argname.replace('_', '-')}",
                    f"-{abbrevs[argname]}",
                    help=param["description"],
                    default=param["value"],
                    type=str_to_bool,
                    required=param["mandatory"],
                    nargs=param["nargs"],
                )
        else:
            if param["type"] in type_map:
                param_type = type_map[param["type"]]
            else:
                print(
                    f"Warning: Argument {argname} of type {param['type']} could not be mapped to a Python base type and thus will not be type-checked."
                )
                param_type = None

            parser.add_argument(
                f"--{argname.replace('_', '-')}",
                f"-{abbrevs[argname]}",
                help=param["description"],
                default=param["value"],
                type=param_type,
                choices=param["choices"],
                required=param["mandatory"],
                nargs=param["nargs"],
            )


def manifest_to_argparser(
    manifest, exit_on_error=True, allow_conf_yaml=False, unmatched_args="error"
):
    # If it's a single function treat it like the old code
    if "functions" in manifest and len(manifest["functions"]) == 1:
        manifest = manifest["functions"][0]

    if "functions" in manifest:
        try:
            parser = argparse.ArgumentParser(
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                exit_on_error=exit_on_error,
            )
        except Exception:
            parser = argparse.ArgumentParser(
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )

        subparsers = parser.add_subparsers(help="sub-command help")
        for ff in manifest["functions"]:
            subp = subparsers.add_parser(
                ff["name"],
                description=ff["description"],
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )
            _add_params_to_parser(subp, ff["params"], allow_conf_yaml, unmatched_args)
    else:
        try:
            parser = argparse.ArgumentParser(
                manifest["name"],
                description=manifest["description"],
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                exit_on_error=exit_on_error,
            )
        except Exception:
            parser = argparse.ArgumentParser(
                manifest["name"],
                description=manifest["description"],
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )
        _add_params_to_parser(
            parser, manifest["params"], allow_conf_yaml, unmatched_args
        )

    return parser


def str_to_bool(value):
    if isinstance(value, bool):
        return value
    if value.lower() == "false":
        return False
    if value.lower() == "true":
        return True
    raise RuntimeError(f"Invalid boolean value {value}")


def get_manifest(file, parser, pm_mode=True, cwl=False):
    import json
    import os

    if cwl:
        return get_manifest_cwl(file, parser)

    manifest = OrderedDict()
    manifestf = os.path.join(os.path.dirname(file), "manifest.json")
    if os.path.exists(manifestf):
        with open(manifestf, "r") as f:
            manifest = json.load(f)

    parserargs = []
    parseractions = parser._actions

    for action in parseractions:
        # skip the hidden arguments, the excluded args and the help argument
        if action.help == "==SUPPRESS==" or action.dest in ("help",):
            continue
        actiondict = OrderedDict()
        actiondict["mandatory"] = action.required
        actiondict["type"] = action.type.__name__ if action.type is not None else "bool"
        actiondict["name"] = action.dest
        actiondict["value"] = action.default
        actiondict["tag"] = action.option_strings[0]
        actiondict["description"] = action.help
        actiondict["nargs"] = action.nargs if action.nargs != 0 else None
        actiondict["choices"] = action.choices
        actiondict["metavar"] = action.metavar

        parserargs.append(actiondict)

    if "name" not in manifest:
        manifest["name"] = parser.prog
    if "version" not in manifest:
        manifest["version"] = "1"
    manifest["description"] = parser.description
    manifest["params"] = parserargs

    return manifest


def get_manifest_cwl(file, parser):
    import json
    import yaml
    import os

    map_argtypes = {
        "str": "string",
        "bool": "boolean",
        "float": "float",
        "int": "int",
        "Path": "File",
    }

    manifest = {"label": parser.prog, "doc": parser.description}
    manifest.update({"cwlVersion": "v1.2", "class": "CommandLineTool", "inputs": {}})

    manifestf = os.path.join(os.path.dirname(file), "manifest.cwl")
    if os.path.exists(manifestf):
        with open(manifestf, "r") as f:
            manifest.update(yaml.load(f, Loader=yaml.FullLoader))
    else:
        manifestf = os.path.join(os.path.dirname(file), "manifest.json")
        if os.path.exists(manifestf):
            with open(manifestf, "r") as f:
                manifest.update(json.load(f))

    parseractions = parser._actions
    for i, action in enumerate(parseractions):
        # skip the hidden arguments, the excluded args and the help argument
        if action.help == "==SUPPRESS==" or action.dest in ("help",):
            continue

        argtype = action.type.__name__ if action.type is not None else "bool"
        argtype = map_argtypes[argtype]

        if action.choices is not None:
            enum_name = f"{action.dest.replace('-', '_')}_enum"
            if "requirements" not in manifest:
                manifest["requirements"] = {}
            if "SchemaDefRequirement" not in manifest["requirements"]:
                manifest["requirements"]["SchemaDefRequirement"] = {}
            if "types" not in manifest["requirements"]["SchemaDefRequirement"]:
                manifest["requirements"]["SchemaDefRequirement"]["types"] = []
            manifest["requirements"]["SchemaDefRequirement"]["types"].append(
                {"type": "enum", "name": enum_name, "symbols": action.choices}
            )
            argtype = enum_name

        if action.nargs:
            argtype += "[]"
        if not action.required:
            argtype += "?"

        manifest["inputs"][action.dest] = {
            "type": argtype,
            "doc": action.help,
            "inputBinding": {
                "position": i,
                "prefix": action.option_strings[0],
            },
        }
        if action.default is not None:
            manifest["inputs"][action.dest]["default"] = action.default

    return manifest


def write_argparser_json(outfile, parser):
    import json

    manifest = get_manifest(outfile, parser, pm_mode=True)

    with open(outfile, "w") as f:
        json.dump(manifest, f, indent=4)
