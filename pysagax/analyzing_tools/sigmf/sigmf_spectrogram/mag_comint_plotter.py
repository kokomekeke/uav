import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import ListedColormap
import numpy as np


cmap = ListedColormap(['#fff0c4','#96ead5'])

file_path = '/home/rp/Documents/DEMO1 - graphs/longages_mag_comint_peaks_seconds.csv' 
df = pd.read_csv(file_path)

df = df[501:1652]
colors = pd.DataFrame(df['color'], dtype="float")

# df[df['peak0dB']<-60] = 0

df['peak0dB'] = df['peak0dB'].apply(lambda x: float("nan") if x < -60 else x)
df['peak1dB'] = df['peak1dB'].apply(lambda x: float("nan") if x < -60 else x) + 7
df['peak2dB'] = df['peak2dB'].apply(lambda x: float("nan") if x < -60 else x)
df['peak3dB'] = df['peak3dB'].apply(lambda x: float("nan") if x < -60 else x) + 7

df['peak0dB'].fillna(method='ffill', inplace=True)
df['peak1dB'].fillna(method='ffill', inplace=True)
df['peak2dB'].fillna(method='ffill', inplace=True)
df['peak3dB'].fillna(method='ffill', inplace=True)



df['datetime'] = pd.to_datetime(df['datetime'])

df['secs'] = (df['datetime'] - df['datetime'].iloc[0]).dt.total_seconds() #elapsed seconds

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(12, 8))

ax1.plot(df['secs'], df['peak0dB'], color='yellow', label='Ch0')
ax1.plot(df['secs'], df['peak1dB'], color='blue', label='Ch1')
ax1.plot(df['secs'], df['peak2dB'], color='green', label='Ch2')
ax1.plot(df['secs'], df['peak3dB'], color='red', label='Ch3')
ax1.set_ylabel('Amplitude')
ax1.legend(loc='upper right')
ax1.margins(x=0)
ax1.grid(True)

ax1.pcolorfast(ax1.get_xlim(), ax1.get_ylim(),
              colors.values[np.newaxis],
              cmap = cmap, alpha = 0.8)


ax2.plot(df['secs'], df['snr'],  label='SNR')
# ax2.set_xlabel('Elapsed Time (seconds)')
ax2.set_ylabel('SNR')
ax2.legend(loc='upper right')
ax2.margins(x=0)
ax2.grid(True)

# ax2.pcolor(df.index[1:], #use data.index to create the proper grid
#           ax2.get_ylim(),
#           colors.values[np.newaxis], 
#           cmap = cmap, alpha = 0.4, 
#           linewidth=0, antialiased=True)

ax2.pcolorfast(ax2.get_xlim(), ax2.get_ylim(),
              colors.values[np.newaxis],
              cmap = cmap, alpha = 0.8)

ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f} dB'))
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f} dB'))
# ax2.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))

ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x/60)}:{int(x)%60:02d}'))
ax1.set_xticks(df["secs"][::30]) 

plt.xticks(rotation=45)
ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x/60)}:{int(x)%60:02d}'))
ax2.set_xticks(df["secs"][::30]) 
plt.xticks(rotation=45)


ax1.set_title(f'Longages flight on 28th Feb 2024')
# Show the plot
plt.tight_layout()
plt.show()
