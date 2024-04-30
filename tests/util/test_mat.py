from pysagax.util.mat import *
import pytest
import numpy as np


@pytest.mark.parametrize(
    "params, expected",
    [
        ((1, 1, 0), 0),
        ((-2.8, 4, 3), 3.2),
        ((1,), 1),
        ((2,), 2),
        ((4 * np.pi,), 0),
        ((-np.pi,), -np.pi),
        ((+np.pi,), -np.pi),
    ],
)
def test_normalize_angle(params, expected):
    result = normalize_angle(*params)
    assert result == expected


@pytest.mark.parametrize(
    "params, expected",
    [
        ((1, 0, 1), 0),
        ((1, 1, 1), 1),
    ],
)
def test_normalize_angle_invalid_params(params, expected):
    with pytest.raises(AssertionError):
        normalize_angle(*params)
