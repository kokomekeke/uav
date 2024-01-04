from typing import Literal


def en_if(cond: bool) -> Literal["normal", "active", "disabled"]:
    """
    Maps a boolean value to the tkinter enable/disable literal.
    :param cond:
    :return:
    """
    if cond:
        return "normal"
    else:
        return "disabled"
