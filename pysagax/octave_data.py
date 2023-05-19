from datetime import datetime

import numpy as np
import numpy.typing as npt


def save_octave(filename: str, variables: dict[str, npt.NDArray[np.float64]]) -> None:
    with open(filename, "w") as f1:
        f1.writelines(
            "\n".join(
                [
                    "# Created by SagaxPyClient, " + str(datetime.now()),
                    "",
                ]
            )
        )
        for name, value in variables.items():
            f1.writelines(
                "\n".join(
                    [
                        f"# name: {name}",
                        "# type: matrix",
                        "# rows: " + str(value.shape[0]),
                        "# columns: " + str(value.shape[1]),
                    ]
                )
            )
            f1.write("\n")
            f1.writelines("\n".join([" ".join(row.astype(str)) for row in value]))
            f1.write("\n\n")
