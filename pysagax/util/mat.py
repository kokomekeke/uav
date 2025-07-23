import numpy as np
import numpy.typing as npt
import pyquaternion
from math import atan2, asin, log, floor

from scipy.spatial.transform import Rotation


def rotation_matrix_from_vectors(
    vec1: npt.NDArray[np.float64], vec2: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Find the rotation matrix that aligns vec1 to vec2
    :param vec1: A 3d "source" vector
    :param vec2: A 3d "destination" vector
    :return mat: A transform matrix (3x3) which when applied to vec1, aligns it with vec2.
    """
    a, b = (vec1 / np.linalg.norm(vec1)).reshape(3), (
        vec2 / np.linalg.norm(vec2)
    ).reshape(3)
    v = np.cross(a, b)
    c = np.dot(a, b)
    s = np.linalg.norm(v)
    kmat = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    rotation_matrix: npt.NDArray[np.float64] = (
        np.eye(3) + kmat + kmat.dot(kmat) * ((1 - c) / (s**2))
    )
    return rotation_matrix


SI_PREFIX_TO_MAGNITUDE = {
    "y": 1e-24,  # yocto
    "z": 1e-21,  # zepto
    "a": 1e-18,  # atto
    "f": 1e-15,  # femto
    "p": 1e-12,  # pico
    "n": 1e-9,  # nano
    "u": 1e-6,  # micro
    "m": 1e-3,  # mili
    "c": 1e-2,  # centi
    "d": 1e-1,  # deci
    "k": 1e3,  # kilo
    "M": 1e6,  # mega
    "G": 1e9,  # giga
    "T": 1e12,  # tera
    "P": 1e15,  # peta
    "E": 1e18,  # exa
    "Z": 1e21,  # zetta
    "Y": 1e24,  # yotta
}

# swap keys and values in prefix mapping
SI_MAGNITUDE_TO_PREFIX = dict((val, key) for key, val in SI_PREFIX_TO_MAGNITUDE.items())


def si_to_float(si: str) -> float:
    """
    Convert a string containing a number with an SI prefix to float.
    eg: 300M -> 3000000.0
    si: must be string!
    """
    if si == "":
        return 0
    si = si.strip()
    if si[-1] in SI_PREFIX_TO_MAGNITUDE.keys():
        return float(si[:-1]) * SI_PREFIX_TO_MAGNITUDE[si[-1]]
    else:
        return float(si)


def float_to_si(number: float | int, dont_round: bool = False) -> str:
    """
    Convert number to a string with SI prefix, eg.: 123456 -> 123.456k

    number: number to convert
    dont_round: if set to true, the result string won't be rounded to at most 9 digits.
    """
    try:
        exponent = floor(log(abs(number), 1000))
        magnitude = 1000 ** (exponent)
        mantissa = number / magnitude

        si_prefix = SI_MAGNITUDE_TO_PREFIX[magnitude]
        # rounding and removing trailing zeros of mantissa to get rid of annoying floating point
        if not dont_round:
            mantissa_str = (format(mantissa, ".9f")).rstrip("0").rstrip(".")
        else:
            mantissa_str = str(mantissa)
        return mantissa_str + si_prefix
    except:  # if no prefix is defined or number==0 or number is already an SI string
        return str(number)


def normalize_angle(angle: float, high: float = np.pi, low: float = -np.pi) -> float:
    assert high > low
    span = high - low
    while angle >= high:
        angle = angle - span
    while angle < low:
        angle = angle + span
    return angle


def ypr(w, x, y, z, degrees=False):
    """Convert quaternion to Euler angles"""
    try:
        a = Rotation.from_quat([x, y, z, w])
    except ValueError:  # 0-norm quaternions or nans
        return [float("nan")] * 3
    return a.as_euler("ZYX", degrees=degrees)


def quat(y, p, r, degrees=False):
    """Convert Euler angles to quaternion in scalar-first form: [w, x, y, z]"""
    a = Rotation.from_euler("ZYX", [y, p, r], degrees=degrees)
    q_scalar_last = a.as_quat()
    q = np.concatenate((q_scalar_last[-1:], q_scalar_last[:-1]))
    return q


def yaw_pitch_roll_from_quaternion(quaternion: list[float]) -> list[float]:
    """
    Only tested for yaw!
    """

    qw, qx, qy, qz = quaternion
    yaw = atan2(2.0 * (qy * qz + qw * qx), qw * qw - qx * qx - qy * qy + qz * qz)
    pitch = asin(-2.0 * (qx * qz - qw * qy))
    roll = atan2(2.0 * (qx * qy + qw * qz), qw * qw + qx * qx - qy * qy - qz * qz)
    return roll, pitch, yaw  # results are in wrong order!
    return yaw, pitch, roll


def has_close_elements(list1, list2, threshold):
    """
    Determines if two lists have any pair of elements with a
    difference of less than the given threshold.

    TODO: add tests
    """
    list1.sort()
    list2.sort()

    i, j = 0, 0
    while i < len(list1) and j < len(list2):
        diff = abs(list1[i] - list2[j])
        if diff < threshold:
            return True
        elif list1[i] < list2[j]:
            i += 1
        else:
            j += 1

    return False
