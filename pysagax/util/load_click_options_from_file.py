

import click
from click import Parameter

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import os

def load_click_options_from_file(ctx, param, conf_path):
    """
    Overwrites the default values for click options from the given config file.
    These values can be further overwritten by providing specifying them in the terminal.

    Load the TOML config file and convert default_map values appropriately for Click,
    including automatic handling of (str, str), multiple=True parameters by converting
    dicts into lists of tuples.
    """
    if not os.path.exists(conf_path):
        print(f"Config file wasn't found at '{conf_path}'")
        return conf_path

    with open(conf_path, "rb") as f:
        conf = tomllib.load(f)

    # Loop through the defined parameters of the command for being able to load dicts
    for p in ctx.command.params:
        if isinstance(p, Parameter) and getattr(p, "multiple", False):
            # If the type is a tuple (e.g., (str, str)), handle dict-to-tuples conversion
            if getattr(p.type, "types", None) == (click.STRING, click.STRING):
                val = conf.get(p.name)
                if isinstance(val, dict):
                    conf[p.name] = list(val.items())

    ctx.default_map = conf
    return conf_path
