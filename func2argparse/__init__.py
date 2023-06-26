import argparse
from func2argparse import _version

__version__ = _version.get_versions()["version"]


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
    name = lines[0].strip().split()[0]

    description = []
    for line in lines[1:]:
        if line.strip().startswith("Parameters"):
            break
        if len(line.strip()):
            description.append(line.strip())
    description = " ".join(description)

    argdocs = {}
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


def func_to_manifest(func, file=None, pm_mode=True):
    from collections import OrderedDict
    import json
    import yaml
    import os
    import inspect
    from typing import get_origin, get_args

    # Read existing manifest if it exists
    manifest = OrderedDict()

    if file is not None:
        manifestf = os.path.join(os.path.dirname(file), "manifest.json")
        if os.path.exists(manifestf):
            with open(manifestf, "r") as f:
                manifest = json.load(f)
        manifestf = os.path.join(os.path.dirname(file), "manifest.yaml")
        if os.path.exists(manifestf):
            with open(manifestf, "r") as f:
                manifest = yaml.load(f, Loader=yaml.FullLoader)

    # Get function signature and documentation
    sig = inspect.signature(func)
    doc = func.__doc__
    if doc is None:
        raise RuntimeError("Could not find documentation in the function...")

    argdocs, description, name = _parse_docs(doc)

    if "name" not in manifest:
        manifest["name"] = name
    if "version" not in manifest:
        manifest["version"] = "1"
    manifest["description"] = description

    arguments = []
    for argname in sig.parameters:
        if argname[0] == "_" or argname in ("args", "kwargs"):
            continue  # Don't add underscore arguments to argparser or args, kwargs
        params = sig.parameters[argname]

        if argname not in argdocs:
            raise RuntimeError(
                f"Could not find help for argument {argname} in the docstring of the function. Please document it."
            )

        argtype = params.annotation
        nargs = None
        # This is needed for compound types like: list[str]
        if get_origin(params.annotation) is not None:
            origtype = get_origin(params.annotation)
            argtype = get_args(params.annotation)[0]
            if origtype in (list, tuple):
                nargs = "+"

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

        if argtype == bool and default:
            raise RuntimeError(
                "func2argparse does not allow boolean flags with default value True"
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

    manifest["params"] = arguments

    # TODO: Deprecate these
    if pm_mode:
        if "specs" not in manifest:
            if (
                "resources" in manifest
                and "ngpu" in manifest["resources"]
                and manifest["resources"]["ngpu"] > 0
            ):
                manifest["specs"] = '{"app": "play1GPU"}'
            else:
                manifest["specs"] = '{"app": "play0GPU"}'
        if "api_version" not in manifest:
            manifest["api_version"] = "v1"
        if "container" not in manifest:
            manifest["container"] = f"{manifest['name']}_v{manifest['version']}"
        if "periodicity" not in manifest:
            manifest["periodicity"] = 0

    return manifest


def manifest_to_argparser(
    manifest, exit_on_error=True, allow_conf_yaml=False, unmatched_args="error"
):
    from pathlib import Path

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
    if allow_conf_yaml:
        parser.add_argument(
            "--conf",
            help="Configuration YAML file to set all parameters",
            type=open,
            action=lambda *x, **y: LoadFromFile(*x, **y, unmatched_args=unmatched_args),
        )

    # Calculate abbreviations
    abbrevs = _get_name_abbreviations([x["name"] for x in manifest["params"]])

    type_map = {"Path": Path, "bool": bool, "int": int, "float": float, "str": str}

    for param in manifest["params"]:
        argname = param["name"]
        if param["type"] == "bool":
            if param["nargs"] is None:
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
            parser.add_argument(
                f"--{argname.replace('_', '-')}",
                f"-{abbrevs[argname]}",
                help=param["description"],
                default=param["value"],
                type=type_map[param["type"]],
                choices=param["choices"],
                required=param["mandatory"],
                nargs=param["nargs"],
            )

    return parser


# DEPRECATED
def func_to_argparser(
    func, exit_on_error=True, allow_conf_yaml=False, unmatched_args="error"
):
    import inspect
    from typing import get_origin, get_args

    sig = inspect.signature(func)
    doc = func.__doc__
    if doc is None:
        raise RuntimeError("Could not find documentation in the function...")

    argdocs, description, name = _parse_docs(doc)

    try:
        parser = argparse.ArgumentParser(
            name,
            description=description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            exit_on_error=exit_on_error,
        )
    except Exception:
        parser = argparse.ArgumentParser(
            name,
            description=description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
    if allow_conf_yaml:
        parser.add_argument(
            "--conf",
            help="Configuration YAML file to set all parameters",
            type=open,
            action=lambda *x, **y: LoadFromFile(*x, **y, unmatched_args=unmatched_args),
        )

    # Calculate abbreviations
    abbrevs = _get_name_abbreviations(sig.parameters)

    for argname in sig.parameters:
        if argname[0] == "_" or argname in ("args", "kwargs"):
            continue  # Don't add underscore arguments to argparser or args, kwargs
        params = sig.parameters[argname]

        if argname not in argdocs:
            raise RuntimeError(
                f"Could not find help for argument {argname} in the docstring of the function. Please document it."
            )

        argtype = params.annotation
        nargs = None
        # This is needed for compound types like: list[str]
        if get_origin(params.annotation) is not None:
            origtype = get_origin(params.annotation)
            argtype = get_args(params.annotation)[0]
            if origtype in (list, tuple):
                nargs = "+"

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

        if argtype == bool:
            if nargs is None:
                if default:
                    raise RuntimeError(
                        "func2argparse does not allow boolean flags with default value True"
                    )
                parser.add_argument(
                    f"--{argname.replace('_', '-')}",
                    f"-{abbrevs[argname]}",
                    help=argdocs[argname]["doc"].strip(),
                    action="store_true",
                )
            else:
                parser.add_argument(
                    f"--{argname.replace('_', '-')}",
                    f"-{abbrevs[argname]}",
                    help=argdocs[argname]["doc"].strip(),
                    default=default,
                    type=str_to_bool,
                    required=params.default == inspect._empty,
                    nargs=nargs,
                )
        else:
            help = argdocs[argname]["doc"].strip()
            choices = argdocs[argname]["choices"]
            parser.add_argument(
                f"--{argname.replace('_', '-')}",
                f"-{abbrevs[argname]}",
                help=help,
                default=default,
                type=argtype,
                choices=choices,
                required=params.default == inspect._empty,
                nargs=nargs,
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
    from collections import OrderedDict
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

    # TODO: Deprecate these
    if pm_mode:
        if "specs" not in manifest:
            if (
                "resources" in manifest
                and "ngpu" in manifest["resources"]
                and manifest["resources"]["ngpu"] > 0
            ):
                manifest["specs"] = '{"app": "play1GPU"}'
            else:
                manifest["specs"] = '{"app": "play0GPU"}'
        if "api_version" not in manifest:
            manifest["api_version"] = "v1"
        if "container" not in manifest:
            manifest["container"] = f"{manifest['name']}_v{manifest['version']}"
        if "periodicity" not in manifest:
            manifest["periodicity"] = 0

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
