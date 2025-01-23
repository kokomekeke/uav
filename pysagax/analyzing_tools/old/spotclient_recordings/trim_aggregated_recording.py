import pandas as pd
import numpy as np

folder = "C:\\Users\\p\\Documents\\measurments\\ocsa_231109\\1\\2\\"
client_data_file = "20231109_145447_merged.csv"

def normalize_angle(angle: float, high: float=np.pi, low: float=-np.pi) -> float:
    span = high - low
    while angle >= high:
        angle = angle - span
    while angle < low:
        angle = angle + span
    return angle

measures = pd.read_csv(f"{folder}{client_data_file}")

measures["keep_rows"] = measures["df_angle_mean"].diff()
measures["keep_rows"][0] = 1
measures = measures[measures["keep_rows"] != 0]
# measures["df_angle"] = measures["df_angle_mean"]

# measures["angle_error_deg"] = measures["df_angle"] * 180 / np.pi - measures["azim"]

# measures["angle_error_deg"] = measures["angle_error_deg"].apply(lambda x: normalize_angle(x, high=180, low=-180))
# measures["angle_eror_abs_deg"] = measures["angle_error_deg"].apply(lambda x: abs(x))

measures.to_csv(f"{folder}{client_data_file[:-4]}_trimmed.csv")
