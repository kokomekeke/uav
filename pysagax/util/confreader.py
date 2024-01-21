def confreader(conf: dict, keys: list, default_value=None):
    """
    Recursively find an element in a nested list.
    Return a default value instead of an exception if the keys don't point to an existing element.
    """
    assert type(conf) is dict
    assert type(keys) is list and len(keys)
    if keys[0] not in conf:  # key not defined in config file
        return default_value
    if len(keys) == 1:  # last key in original key list -> return its value
        return conf[keys[0]]
    if type(conf[keys[0]]) is not dict:  # keys are deeper than the actual nested dict
        return default_value
    return confreader(conf[keys[0]], keys[1:], default_value)
