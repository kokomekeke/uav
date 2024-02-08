from typing import Any
from pysagax.util.read_from_conf import *
import pytest

test_conf: dict[str, Any] = {"a": None, "b": 1, "c": {"x": None, "y": 2, "z": {}}}


@pytest.mark.parametrize(
    "params, expected",
    [
        ((test_conf, ["a"], -1), None),  # 0:
        ((test_conf, ["a", "b"], -1), -1),  # 1:
        ((test_conf, ["b"], -1), 1),  # 2:
        ((test_conf, ["b", "a"], -1), -1),  # 3:
        ((test_conf, ["c", "x"], -1), None),  # 4:
        ((test_conf, ["c", "y"], -1), 2),  # 5: valid keys
        ((test_conf, ["c", "z"], -1), {}),  # 6: empty dict result
        ((test_conf, ["c", "z", "w"], -1), -1),  # 7: invalid keys
        ((test_conf, ["d", "z", "w"], -1), -1),  # 8: invalid keys
        (({}, ["d", "z", "w"], -1), -1),  # 9: empty dict imput
        ((test_conf, ["c", "y"]), 2),  # 10: no default value, valid keys
        ((test_conf, ["c", "z"]), {}),  # 11: no default value, empty dict result
        ((test_conf, ["c", "z", "w"]), None),  # 12: no default value, invalid keys
        ((test_conf, ["d", "z", "w"]), None),  # 13: no default value, invalid keys
    ],
)
def test_read_from_conf(params: tuple[dict[Any, Any], list[str], Any], expected: Any):
    result = read_from_conf(*params)
    assert result == expected


@pytest.mark.parametrize(
    "params, expected",
    [
        (("not a dict", [], -1), -1),
        (("not a dict", ["a"], -1), -1),
        ((test_conf, [], -1), -1),
        ((None, ["a"], -1), -1),
    ],
)
def test_read_from_conf_invalid_conf(params: tuple[Any, list[str], Any], expected: Any):
    with pytest.raises(AssertionError):
        read_from_conf(*params)


@pytest.mark.parametrize(
    "params, expected",
    [
        ((test_conf, 10, -1), -1),
        ((test_conf, "abc", -1), -1),
    ],
)
def test_read_from_conf_invalid_keys(params: tuple[dict[Any, Any], Any, Any], expected):
    with pytest.raises(AssertionError):
        read_from_conf(*params)
