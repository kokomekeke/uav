import pytest
from pysagax.ui.plot_frame import PlotFrame
from pytest_mock import mocker
import numpy as np


def get_plot_frame_object():
    """
    creates a PlotFrame object without calling PlotFrame.__init__()
    to test methods that don't requre initialization
    """
    pf_mock = object.__new__(PlotFrame)
    return pf_mock


@pytest.mark.parametrize(
    ["spectrum", "wanted_bc", "expected_result"],
    [
        [[0, 1, 2, 3, 4, 5], 10, [0, 0, 0, 1, 2, 3, 4, 5, 0, 0]],  # extend even
        [[0, 1, 2, 3, 4, 5], 11, [0, 0, 0, 1, 2, 3, 4, 5, 0, 0, 0]],  # extend odd
        [[0, 1, 2, 3, 4, 5], 6, [0, 1, 2, 3, 4, 5]],  # no action
        [[0, 1, 2, 3, 4, 5], 4, [1, 2, 3, 4]],  # truncate even
        [[0, 1, 2, 3, 4, 5], 3, [1, 2, 3]],  # truncate odd
    ],
)
def test_squeeze_spectrum_to_plot(spectrum, wanted_bc, expected_result, mocker):
    # arrange
    pf = get_plot_frame_object()
    # mock called functions
    mock_warn_extend = mocker.patch("pysagax.ui.plot_frame.PlotFrame._warn_extend")
    mock_warn_truncate = mocker.patch("pysagax.ui.plot_frame.PlotFrame._warn_truncate")

    # act & assert
    result = pf.squeeze_spectrum_to_plot(spectrum, len(spectrum), wanted_bc)
    if len(spectrum) < wanted_bc:
        mock_warn_extend.assert_called()
    if len(spectrum) > wanted_bc:
        mock_warn_truncate.assert_called()
    assert np.all(result == expected_result)
    assert len(result) == wanted_bc
