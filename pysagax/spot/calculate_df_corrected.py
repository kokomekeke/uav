from typing import Optional

from pysagax.util.mat import normalize_angle


def calculate_df_corrected(
    df_value: Optional[float], compass_heading: Optional[float]
) -> Optional[float]:
    """
    Offsets DF bearing angle by compass heading
    :param df_value: DF bearing angle [rad]
    :param compass_heading: Heading angle of the compass [rad] [North=0]
    :return: corrected DF angle [rad]
    """
    df_corrected = None
    if df_value is not None:
        if compass_heading is not None:
            df_corrected = normalize_angle(compass_heading + df_value)
    return df_corrected
