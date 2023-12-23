from typing import Optional

from pysagax.util.mat import normalize_angle

# def calculate_df_corrected(df_value, compass_heading, encoder_heading):
#     df_corrected_from_compass = (
#         conf["defaults"]["df_corrected_from_compass"] if conf else True
#     )
#     df_corrected = None
#     if df_value is not None:
#         if df_corrected_from_compass and compass_heading is not None:
#             df_corrected = normalize_angle(compass_heading + df_value)
#         if not df_corrected_from_compass and encoder_heading is not None:
#             df_corrected = normalize_angle(encoder_heading + df_value)
#     return df_corrected


def calculate_df_corrected(
    df_value: Optional[float], compass_heading: Optional[float]
) -> Optional[float]:
    df_corrected = None
    if df_value is not None:
        if compass_heading is not None:
            df_corrected = normalize_angle(compass_heading + df_value)
    return df_corrected
