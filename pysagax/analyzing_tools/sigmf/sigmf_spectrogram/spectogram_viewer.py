import numpy as np
import argparse
import matplotlib
from  matplotlib import pyplot as plt


parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input_file', dest='input_file', help='A spectrogram file (npy archive)', default='spectogram.npy')
args = parser.parse_args()

print(f"Loading spectogram {args.input_file}")
spectrogram = np.load(args.input_file)

vmax = 0
vmin = -120
fig, ax = plt.subplots()


# image = plt.imshow(
image = ax.imshow(
    spectrogram,
    cmap=matplotlib.cm.get_cmap("gnuplot"),  # type: ignore
    animated=True,
    vmax=vmax,
    vmin=vmin,
)
plt.colorbar(image) 


plt.show(block=True)    