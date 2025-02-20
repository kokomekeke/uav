"""
the .detectrec files has empty detection.roiId fields for when we detected a signal that has roi

eg: if detection1.roiId is empty, but detection1.frequency is not, that means that detection1.roiId should be 0

"""

import pandas as pd
import numpy as np
from typing import Optional

# def

# df = pd.read_csv('/media/rp/data/recordings/240717 Toulouse/detectrec/20240717_143012/spotrecording.csv')
df = pd.read_csv('/media/rp/data/recordings/240717 Toulouse/detectrec/20240717_151148/spotrecording.csv')

print(df.keys())
roi_id_cols = [k for k in df.keys() if k.endswith("roiId")] # find columns like: detectionX.roiId (X is an integer)
detection_freq_cols  = [".".join(k.split(".")[:-1] + ["frequency"]) for k in roi_id_cols] # find the corresponding detectionX.frequency
print(roi_id_cols)
print(detection_freq_cols)

for f_key, id_key in zip(detection_freq_cols, roi_id_cols):
    df[id_key] = df.apply(lambda r: int(0) if np.isnan(r[id_key]) and not np.isnan(r[f_key]) else r[id_key], axis=1) # roiId is 0 if it hasn't been set but other field(frequency) in the detection has been
    # df[id_key] = df[id_key].astype(Optional[int])


# df.to_csv('/media/rp/data/recordings/240717 Toulouse/detectrec/20240717_143012/spotrecording_roiId.csv', index=False, )
df.to_csv('/media/rp/data/recordings/240717 Toulouse/detectrec/20240717_151148/spotrecording_roiId.csv', index=False, )