# README #

Simple test client for CoreService written in Python.

## Requirements

 * Python3 with tkinter

### Required pip packages

 * Numpy
 * Matplotlib

### Additional required pip packages for compass sensors

 * scipy
 * pyusb
 * pyftdi
 * ahrs
 * pyquaternion


```bash
pip install -r requirements.txt
```

# CS Test Client

Confluence page: https://sagaxcommunications.atlassian.net/wiki/spaces/WBDF/pages/88637445/Forgatott+antenn+s+m+r+s#M%C3%A9r%C3%A9s-l%C3%A9p%C3%A9sei

## How to use

Start `cstestclient.py` using Python 3.

```bash
python cstestclient.py
```

![alt text](screenshot.png)

 1. Fill the *Command host* and *Stream host* textboxes in `<hostname>:<tcp port>` format.
 2. Click the *Connect* button and make sure the status bar (bottom) says `Connected`.
 3. Send the desired commands to the CoreService via the command input box. Press the Return (Enter) key to send.
    * Use the autocomplete feature: press the *Tab* key to fill in the first suggestion, use the *Up*/*Down* key to browse the suggestions.
    * Command history are stored as suggestions in the `commands.txt` file.
 4. Magnitude waterfall plot, azimuth and elevation plots can be observed in the middle panel. Use the toolbar to interact with the plots.


## Options

Display only 2048 bins and 100 packets on the graph with 10 frames per second (useful on slower machines):

```bash
python cstestclient.py --bin 2048 --wf 100 --fps 10
```

Display packet types only and do not show matplotlib graphs at all:

```bash
python cstestclient.py --no-disp
```

Display ROI azimuth and elevation waterfall instead of spectrum:

```bash
python cstestclient.py --roi-wf
```

Include ROI antenna phase differences on the azimuth and elevation waterfall:

```bash
python cstestclient.py --roi-wf --phases-roi-wf
```

Use a compass sensor on serial port `COM1`:
```bash
python cstestclient.py --roi-wf --sensor-dev COM1
```

# Compass tester

Confluence page: https://sagaxcommunications.atlassian.net/wiki/spaces/BP/pages/111640592/Aaronia+ir+nyt+szenzor+kalibr+l+szoftver

## How to use

Start `compass_tester.py` using Python 3. Specify the sensor type in the command line arguments.

```bash
python compass_tester.py --sensor-dev COM1
```

```bash
python compass_tester.py --aaronia
```

# Measurement utility

Confluence page: https://sagaxcommunications.atlassian.net/wiki/spaces/WBDF/pages/111575041/M+r+si+seg+dprogram

## How to use

Start `measurement_utility.py` using Python 3. Specify the data folders in the command line arguments.

```
pythonw.exe C:\Users\sgx\Documents\sgx-pc\measurement_utility.py --octave-dir "C:\Users\sgx\Documents\sgx-pc" --tdms-dir "C:\Users\sgx\Documents\LENA\CurrentVersion\cs64" --measurement-dir "C:\Users\sgx\Documents\Meresek\JelenlegiMeres"
```

```bash
python measurement_utility.py --octave-dir . --tdms-dir ../sgx-cs/build --measurement-dir ../measurements
```
