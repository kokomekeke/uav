"""
Generate spectrograms from all sigmf recording folders that are in a directory. 
(eg. an entire field day.)


To save the spectrograms as png images, modify the end of sigmfspectrum.py like this:

            # plt.show(block=True if len(show) >= plots_shown else False)
            title = filename.split("/")[-2]
            fig.suptitle(f"{title}")
            fig.savefig(f"/home/rp/Documents/sgx-pc/pysagax/gany/spectrograms/{title}_spectrogram.png", dpi=500,)
            plt.show(block=False)
"""
import os
import sys
import subprocess

def find_subdirs(directory):
    subdirectories = []
    for root, dirs, files in os.walk(directory):
        for subdir in dirs:
            subdirectories.append(os.path.join(root, subdir))
    return subdirectories

def call_sigmspectrum(subdir):
    try:
    # python pysagax/sigmfspectrum.py --show 0 --stride 560000 --fftsize 1024 /mnt/largeshare/group/__projects/LENA/03_Technical/Measurements/2023-11-13-Ocsa-RAC/Field1Drone/CSRecordings/20231113_Mon_130717/
        print("SPECTROGRAM FOR ", subdir)
        subprocess.run(['python', '../../sigmfspectrum.py', '--show', '0',  '--stride', '56000', '--fftsize', '1024', subdir], check=True)
        # subprocess.run(['python pysagax/sigmfspectrum.py --show 0 --stride 560000 --fftsize 1024 ', subdirectory], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while processing {subdir}: {e}")

def main(dir):
    if not os.path.isdir(dir):
        print(f"Error: {dir} doesn't exist.")
        sys.exit(1)

    subdirs = find_subdirs(dir)
    subdirs.sort()
    for subdir in subdirs:
        call_sigmspectrum(subdir)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python gen_spectrograms.py <directory>")
        sys.exit(1)

    dir = sys.argv[1]
    main(dir)
