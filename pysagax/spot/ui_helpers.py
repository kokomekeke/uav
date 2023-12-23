from typing import Literal


def en_if(cond: bool) -> Literal["normal", "active", "disabled"]:
    if cond:
        return "normal"
    else:
        return "disabled"
