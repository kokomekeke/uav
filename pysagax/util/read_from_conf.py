from typing import Any


def read_from_conf(conf: dict[str, Any], keys: list[str], default_value: Any =None):
    """
    Recursively find an element in a nested dictionary.
    Return a default value instead of an exception if the keys don't point to an existing element.

    conf: a dictionary (parsed from a .toml file)
    keys: list of keys. 
            eg trying to access conf['a']['b'] -> use read_from_conf(conf, ['a', 'b'])
    """
    assert type(conf) is dict
    assert type(keys) is list and len(keys)
    if keys[0] not in conf:  # key not defined in config file
        return default_value
    if len(keys) == 1:  # last key in original key list -> return its value
        return conf[keys[0]]
    if type(conf[keys[0]]) is not dict:  # keys are deeper than the actual nested dict
        return default_value
    return read_from_conf(conf[keys[0]], keys[1:], default_value)
