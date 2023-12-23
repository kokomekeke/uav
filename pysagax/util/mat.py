import numpy as np
import numpy.typing as npt


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


def si_to_float(si: str) -> float:
    prefix = {
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
    si = si.strip()
    if si[-1] in prefix.keys():
        return float(si[:-1]) * prefix[si[-1]]
    else:
        return float(si)


def normalize_angle(angle: float, high: float = np.pi, low: float = -np.pi) -> float:
    span = high - low
    while angle >= high:
        angle = angle - span
    while angle < low:
        angle = angle + span
    return angle
