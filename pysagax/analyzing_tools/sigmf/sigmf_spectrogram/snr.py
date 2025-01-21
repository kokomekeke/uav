import numpy as np
import math
import argparse
import matplotlib
from  matplotlib import pyplot as plt
# from pysagax.util.mat import si_to_float


parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input_file', dest='input_file', help='A spectrogram file (npy archive)', default='spectogram.npy')
parser.add_argument('-o', '--output_file', dest='output_file', help='An image file for the SNR graph', default='snr.png')
parser.add_argument('-rc', '--roi_center', dest='roi_center', help='ROI center frequency ', default=0)
parser.add_argument('-rw', '--roi_span', dest='roi_span', help='ROI eidth frequency ', default=0)
args = parser.parse_args()

def calculate_snr(spectrum, min_freq, max_freq, roi_center, roi_span) -> tuple[float, float]:
    #calculates the SNR for a spectrum
    bin_freqs = np.linspace(min_freq, max_freq, len(spectrum))

    spectrum_wtih_freq = list(zip(bin_freqs, spectrum))

    roi_min = roi_center - roi_span / 2
    roi_max = roi_center + roi_span / 2

    signal_bins = [a for f, a in spectrum_wtih_freq if roi_min < f and f < roi_max]
    noise_bins = [a for f, a in spectrum_wtih_freq if not (roi_min < f and f < roi_max)]
    # print(signal_bins)
    # print(noise_bins)

    if len(signal_bins) == 0 or len(noise_bins) == 0:
        return 0, 0

    signal_db = max(signal_bins)
    noise_db = sum(noise_bins) / len(noise_bins)

    return signal_db, noise_db #not in dB in spectogram files!
def calculate_snr2(spectrum, min_freq, max_freq, roi_center, roi_span) -> tuple[float, float]:
    #calculates the SNR for a spectrum
    bin_freqs = np.linspace(min_freq, max_freq, len(spectrum))

    spectrum_wtih_freq = list(zip(bin_freqs, spectrum))

    roi_min = roi_center - roi_span / 2
    roi_max = roi_center + roi_span / 2

    signal_bins = [a for f, a in spectrum_wtih_freq if roi_min < f and f < roi_max]
    noise_bins = [a for f, a in spectrum_wtih_freq if not (roi_min < f and f < roi_max)]
    print(signal_bins)
    print(noise_bins)

    if len(signal_bins) == 0 or len(noise_bins) == 0:
        return 0, 0

    signal_db = max(signal_bins)
    noise_db = sum(signal_bins)-signal_db / len(noise_bins)

    return signal_db, noise_db #not in dB in spectogram files!

print(f"Loading spectogram {args.input_file}")
spectrogram_file = np.load(args.input_file)
spectrogram = spectrogram_file['spectrum']
try:
    center_freq = spectrogram_file['freq_center']
except:
    center_freq = spectrogram_file['center_freq']

iq_rate = spectrogram_file["sample_rate"]

min_freq = center_freq - iq_rate / 2
max_freq = center_freq + iq_rate / 2

roi_center = int(args.roi_center)#si_to_float(args.roi_center)
roi_span =int(args.roi_span) #si_to_float(args.roi_span)
if roi_center == 0:
    roi_center = center_freq
    roi_span = iq_rate

snr = []
signal_lvl = []
noise_lvl = []
print(spectrogram.shape, spectrogram.shape[0], spectrogram.shape[1])
for spectrum in spectrogram.T:
    signal, noise = calculate_snr(spectrum, min_freq, max_freq, roi_center, roi_span)
    # print(signal, noise)
    signal_lvl.append(10 * math.log10(signal / 32000) if signal > 0 else float("-inf"))
    noise_lvl.append(10 * math.log10(noise / 32000) if noise > 0 else float("-inf"))
    current_snr =  10 * math.log10(signal / noise) if signal / noise > 0 else float("-inf")
    snr.append(max(0, current_snr))

fig, ax =  plt.subplots()
# ax.plot(signal_lvl, label="s")
# ax.plot(noise_lvl, label="n")
time_ax = np.linspace(0, spectrogram.shape[1]/10, spectrogram.shape[1])
ax.plot(time_ax, snr, label="SNR [dB]")
ax.set_title(f'Cessales flight on 29th Feb 2024 at {roi_center/1e6:0.2f}M')
ax.set_ylabel("SNR [dB]")
ax.set_xlabel("time [s]")
ax.legend()

fig.savefig(f"{args.input_file[:-4]}_snr_{roi_center/1e6:0.2f}M.png", dpi=500,)
# plt.show(block=True)

import pandas as pd

df = pd.DataFrame({"snr": snr, "ts": time_ax})
df["ts"] = pd.to_datetime(df['ts'], unit='s')

df['ts'] = df['ts'].dt.floor('S')
# df.groupby(['ts', pd.Grouper(freq='1S', key='ts')], as_index=False) \
#       .agg({'pid': 'first', 'timestamp': 'first', 'value': 'mean'})
df = df.groupby('ts').mean().reset_index()
print(df)
df.to_csv(f"{args.input_file[:-4]}_snr_{roi_center/1e6:0.2f}M.csv")

fig, ax =  plt.subplots()
ax.plot(df['ts'], df["snr"], label="SNR [dB]")
ax.set_title(f'Cessales flight on 29th Feb 2024 at {roi_center/1e6:0.2f}M')
ax.set_ylabel("SNR [dB]")
ax.set_xlabel("time [s]")
ax.legend()


plt.show(block=True)

