# README #

Simple test client for CoreService written in Python.

## Requirements

 * Python3
 * Tkinter
 * Numpy
 * Matplotlib

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


